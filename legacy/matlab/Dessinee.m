clear all
close all
clc


load('VecfileMEM_tst1.mat')


figure()
plot(Tmem,vmem),grid
legend('Edc1','Edc1','Wred','W','Pdc1','Pdc2','Isdref','Isd','alpha','alpha_out')

figure()
plot(Tmem,vmem(:,3:4)),grid
legend('Wred','W')

figure()
plot(Tmem,vmem(:,1:2)),grid
legend('Edc1','Edc1')

figure()
plot(Tmem,vmem(:,5:6)),grid
legend('Pdc1','Pdc2')

figure()
plot(Tmem,vmem(:,7:8)),grid
legend('Isdref','Isd')

figure()
plot(Tmem,vmem(:,9:10)),grid
legend('alpha','alpha_out')

v = vmem;
N = 50; %% sliding window averaging length
for i=1:length(Tmem)-N
    for j=1:10
       v(i,j) = mean(vmem(i:i+N,j));
    end
end

figure()
plot(Tmem,v),grid
legend('Edc1','Edc1','Wred','W','Pdc1','Pdc2','Isdref','Isd','alpha','alpha_out')

figure()
plot(Tmem,v(:,3:4)),grid
legend('Wred','W')

figure()
plot(Tmem,v(:,1:2)),grid
legend('Edc1','Edc1')

figure()
plot(Tmem,v(:,5:6)),grid
legend('Pdc1','Pdc2')

figure()
plot(Tmem,v(:,7:8)),grid
legend('Isdref','Isd')

figure()
plot(Tmem,v(:,9:10)),grid
legend('alpha','alpha_out')
