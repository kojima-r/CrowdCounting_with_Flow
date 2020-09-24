import os
import cv2
import numpy as np
import torch
# import pytorch_memlab
# from utils  import model


class AllLoss():
    def __init__(self, optical_loss_on=1, batchsize=1):
        # super().__init__()
        self.optical_loss_on = optical_loss_on
        self.bathsize = batchsize

    def forward(self, tm_personlabel, t_person_label, tm2t_flow_label,
                output_before_foward, output_before_back,
                output_aftter_foward, output_after_back, alpha=1, beta=1e-4):

        floss = self.flow_loss(output_before_forward=output_before_foward,
                               output_after_forward=output_aftter_foward,
                               label=t_person_label)

        closs = self.cycle_loss(output_before_foward=output_before_foward,
                                output_before_back=output_before_back,
                                output_after_foward=output_aftter_foward,
                                output_after_back=output_after_back)

        loss_combi = floss + alpha * closs

        if self.optical_loss_on == 1:
            oloss = self.optical_loss(
                tm_personlabel,
                tm2t_flow_label,
                output_before_foward)
            loss_combi += beta * oloss

        # loss_combi /= self.bathsize

        """
        floss_nan = (torch.sum(torch.isnan(floss)).item() == 0)
        closs_nan = (torch.sum(torch.isnan(closs)).item() == 0)
        oloss_nan = (torch.sum(torch.isnan(oloss)).item() == 0)

        print("floss_nan: {}, closs_nan: {}, oloss_nan: {}".format(floss_nan, closs_nan, oloss_nan))
        """
        return loss_combi

    def flow_loss(self, output_before_forward, output_after_forward, label):
        est_sum_before = torch.sum(output_before_forward, dim=1, keepdim=True)
        est_sum_after = torch.sum(output_after_forward, dim=1, keepdim=True)

        res_before = label - est_sum_before
        res_after = label - est_sum_after

        se_before = res_before * res_before
        se_after = res_after * res_after

        floss = torch.sum((se_before + se_after)) / self.bathsize

        return floss

    def cycle_loss(self, output_before_foward, output_before_back,
                   output_after_foward, output_after_back):

        res_before = output_before_foward - output_before_back
        res_after = output_after_foward - output_after_back

        se_before = torch.sum(
            (res_before * res_before),
            dim=1,
            keepdim=True) / self.bathsize
        se_after = torch.sum(
            (res_after * res_after),
            dim=1,
            keepdim=True) / self.bathsize

        closs = torch.sum((se_before + se_after)) / self.bathsize

        return closs

    def optical_loss(self, before_person_label, flow_label, flow_output):
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        indisize = before_person_label.size()
        indicator = torch.where(
            before_person_label > 0.9,
            torch.ones(
                indisize[0],
                indisize[1],
                indisize[2],
                indisize[3]).to(device),
            torch.zeros(
                indisize[0],
                indisize[1],
                indisize[2],
                indisize[3]).to(device))
        se = (flow_label - flow_output) * \
            (flow_label - flow_output) / self.bathsize

        loss = torch.sum((indicator * se)) / self.bathsize

        return loss


def output_to_img(output):
    root = os.getcwd()
    imgfolder = root + "/images/"

    output_num = output.detach().cpu().numpy()
    out = output_num[0, 0, :, :]

    heatmap = cv2.resize(out, (out.shape[1]*8, out.shape[0]*8))
    heatmap = np.array(heatmap*255, dtype=np.uint8)

    cv2.imwrite(imgfolder+"test.png", heatmap)


if __name__ == "__main__":
    import model

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    # device = "cpu"
    can_model = model.CANNet(load_weights=True)
    can_model.to(device)
    # reporter = pytorch_memlab.MemReporter(can_model)

    criterion = AllLoss()

    x1 = torch.ones(1, 3, 720, 1280).to(device)
    x2 = torch.ones(1, 3, 720, 1280).to(device)
    x3 = torch.ones(1, 3, 720, 1280).to(device)

    tm_person = torch.zeros(1, 1, 90, 160).to(device)
    t_person = torch.zeros(1, 1, 90, 160).to(device)
    tm2t_flow = torch.zeros(1, 10, 90, 160).to(device)

    with torch.set_grad_enabled(False):
        output_befoer_forward = can_model(x1, x2)
        output_after_forward = can_model(x2, x3)
        output_before_back = can_model(x2, x1)

    with torch.set_grad_enabled(True):
        output_after_back = can_model(x3, x2)

    loss = criterion.forward(tm_person, t_person, tm2t_flow,
                             output_befoer_forward, output_before_back,
                             output_after_forward, output_after_back)
    loss.backward()
    # reporter.report()

    e_loss = loss.item()
    print("loss: {}".format(e_loss))
