close all; clear all; clc
addpath rtb common smtb

%% Compute workspace of robot
L1 = 0.285;
L2 = 0.265;

window_size = 1000; % pixels

DH(1) = Link([0 0 L1 0]);
DH(2) = Link([0 0 L2 0]);
th1 = 0:0.05:pi;
th2 = 0:0.05:pi; % 
% th2 = -pi/2:0.05:pi/2;

q = {th1,th2};
 
plotworkspace(DH,q)
hold on

 
 %% Inverse kinematics for initial position
 
syms L_1 L_2 theta1 theta2 XE YE

XE_RHS = -L_1*sin(theta1) - L_2*cos(theta1+theta2);
YE_RHS = L_1*cos(theta1) - L_2*sin(theta1+theta2);

XE_MLF = matlabFunction(XE_RHS,'Vars',[L_1 L_2 theta1 theta2]);
YE_MLF = matlabFunction(YE_RHS,'Vars',[L_1 L_2 theta1 theta2]);

XE_EQ = XE == XE_RHS;
YE_EQ = YE == YE_RHS;

S = solve([XE_EQ YE_EQ], [theta1 theta2]);

simplify(S.theta1)

TH1_MLF{1} = matlabFunction(S.theta1(1),'Vars',[L_1 L_2 XE YE]);
TH1_MLF{2} = matlabFunction(S.theta1(2),'Vars',[L_1 L_2 XE YE]);
TH2_MLF{1} = matlabFunction(S.theta2(1),'Vars',[L_1 L_2 XE YE]);
TH2_MLF{2} = matlabFunction(S.theta2(2),'Vars',[L_1 L_2 XE YE]);

%% Square workspace
xc = -0.1; yc = -0.16; size = 0.37;    % center and size of square

plot([xc, xc, xc - size, xc - size, xc],....
     [yc, yc + size, yc + size, yc, yc],'LineWidth',2,'color','k')
 
 
trajOffx = (window_size/2-100)/window_size*size;

xi = xc - size/2 + size/2.2;
yi = yc + size/2 - size/2.2;
plot(xi, yi, "b*",'LineWidth',2)


[theta1i, theta2i] = ikInit(xi, yi, L1, L2, TH1_MLF, TH2_MLF)



function [theta1i, theta2i] = ikInit(xi, yi, L1, L2, TH1_MLF, TH2_MLF)
theta1i = TH1_MLF{1}(L1,L2,xi,yi);
theta2i = TH2_MLF{1}(L1,L2,xi,yi);
end