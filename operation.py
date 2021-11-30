from hebi_position import calculate_hebi_position, set_hebi_position, reset_timer, loop_timer
from hebi_functions import initialize_hebi, get_hebi_feedback, send_hebi_position_command, send_hebi_effort_command
from encoder_position import calculate_encoder_position
from encoder_functions import initialize_encoders
from controller_functions import *
from trajectory_functions import Trajectory
from numpy import pi, sin, cos
from os import path
from backlash_functions import smooth_backlash_inverse, load_GPR_param_models, initialize_backlash, inverse_hammerstein
import matplotlib.pyplot as plt


#=== Change these to gather trials ===#
preview_time = 0
oneD = False
type = "hebi"
# type = "controller"
# type = "encoder"
trajectory_type = "chirp2"
backlash_compensation = False
include_GPR = False
model_number = '1'
f = 0.025 # default: 0.025
T = 60

user_cutoff_freq = 0.75
Kp = [50.0, 40.0] # [Kp1, Kp2]

# hammerstein inverse parameters
c_bl = [-0.0572, -0.1487, -0.0702, -0.2219]
K_bl = [0.9803, 0.9748]
tau_bl = [0.1, 0.1, 0.26, 0.38]

# smooth inverse parameters
#bl_cutoff_freq = 0.5
#c_R = [0.02275, 0.043848]
#c_L = [0.18483, 0.314722]
#m = [0.97676, 0.97014]


#=== Global variables ===#

# Link lengths for 2 DOF:
L1 = 0.285
L2 = 0.265

# Initialize user input filter:
O1k_1 = 0 # y1[k-1]
V1k_1 = 0 # v1[k-1]
O2k_1 = 0 # y2[k-1]
V2k_1 = 0 # v2[k-1]

def P_controller(theta,theta_d,Kp):    
    return np.array([Kp[0]*(theta_d[0]-theta[0]), Kp[1]*(theta_d[1]-theta[1])])

def user_input_filter(omega, cutoff_freq=1.0, T=0.01):
    # input freq in hz
    global O1k_1
    global V1k_1
    global O2k_1
    global V2k_1
    tau = 1/(2*pi*cutoff_freq)
    O1 = (omega[0] + V1k_1 - (1-2*tau/T)*O1k_1)/(2*tau/T+1)
    O2 = (omega[1] + V2k_1 - (1-2*tau/T)*O2k_1)/(2*tau/T+1)
    O1k_1 = O1 
    V1k_1 = omega[0]
    O2k_1 = O2
    V2k_1 = omega[1]
    return np.array([O1,O2])

def save_data(output):
    if backlash_compensation:
        comp = "compensated"
    else:
        comp = "uncompensated"
    fs = str(f)
    f_r = fs.replace('.', '')
    save_name = "csv/{}_{}_{}_1.csv".format(type, f_r, comp)
    for i in range(2, 100):
        if path.exists(save_name) is True:
            save_name = "csv/{}_{}_{}_{}.csv".format(type, f_r, comp, i)
        else:
            break

    np.savetxt(save_name, np.array(output), delimiter=",")
    print("Data saved as:", save_name)

def calculate_velocity(theta, joystick, K):
        
       axis = get_axis(joystick)
       axis[1] = -axis[1]

       pos = input_ball.pos
       if pos[0] < input_ball_radius:
           axis[0] = 0.75
       elif pos[0] > window_size - input_ball_radius:
           axis[0] = -0.75
       elif pos[1] < input_ball_radius:
           axis[1] = -0.75
       elif pos[1] > window_size - input_ball_radius:
           axis[1] = 0.75
       theta1 = theta[0]
       theta2 = theta[1]

       Jinv = np.matrix([[-cos(theta1 + theta2)/(L1*cos(theta2)), -sin(theta1 + theta2)/(L1*cos(theta2))],
                         [(L2*cos(theta1 + theta2) + L1*sin(theta1))/(L1*L2*cos(theta2)), (L2*sin(theta1 + theta2) - L1*cos(theta1))/(L1*L2*cos(theta2))]])
       # print("Jinv:", Jinv)
       vel_d = K @ axis
       omega_d = Jinv @ K @ axis
       omega_d = np.squeeze(np.asarray(omega_d))

       return omega_d, vel_d

if __name__ == "__main__":

    print("T:", T)
    joystick = initialize_joystick()
    output = []

    animation_window = create_animation_window()
    animation_canvas = create_animation_canvas(animation_window)
    trajectory = Trajectory(trajectory_type, T, None, window_size)
    print("T in class:", trajectory.T)
    t_max, vel_max = trajectory.max_vel()

    if backlash_compensation:
        if include_GPR:
            GPR_models = load_GPR_param_models(model_number)
        else:
            GPR_models = None


    if type == "hebi" or type == "encoder":

        K_gain = 2
        workspace_size = 0.37
        K = K_gain*(workspace_size/window_size)*vel_max*np.matrix([[1, 0], [0, 1]])
        print("Gain matrix:", K)
        freq = 100 # hz
        group, hebi_feedback, command = initialize_hebi()
        group.feedback_frequency = freq
        theta, omega, torque, hebi_limit_stop_flag = get_hebi_feedback(group, hebi_feedback)
        group_info = group.request_info()
        if group_info is not None:
            group_info.write_gains("csv/saved_gains.xml")
        if trajectory_type == "circle":
            theta1i = 0.2827
            theta2i = 1.0694

        if trajectory_type == "chirp" or trajectory_type == "chirp2":
            theta1i = 1.3728
            theta2i = 0.8586


        set_hebi_position(group, hebi_feedback, command, theta1i, theta2i, type)

    pos_i = trajectory.screen_coordinates(0)
    target_ball = Ball(pos_i, target_ball_radius, "red", animation_canvas)

    line = animation_canvas.create_line(0, 0, 0, 0, fill='red', arrow='last', smooth='true', dash=(6,4))

    if type == "controller":
        gain = 2*vel_max
        print(gain)
        input_ball = Ball(pos_i, input_ball_radius, "white", animation_canvas)
        pos_input = pos_i

    if type == "hebi":
        pos0 = calculate_hebi_position(group, hebi_feedback, offset = 0)
        offset = pos_i - pos0
        input_ball = Ball(calculate_hebi_position(group, hebi_feedback, offset), input_ball_radius, "white", animation_canvas)
        print("Offset 1:", offset)
        # print(calculate_hebi_position(group, hebi_feedback, offset))

    if type == "encoder":
        arduino = initialize_encoders()
        pos0 = calculate_encoder_position(arduino, offset = 0)
        offset = pos_i - pos0
        input_ball = Ball(calculate_encoder_position(arduino, offset), input_ball_radius, "white", animation_canvas)
    
    draw_preview(animation_canvas, line, trajectory, preview_time, T, 0)
    animation_window.update()

    print("Get ready...")
    sleep(1)

    i = 0
    t0 = time()
    t_draw = t0

    # set timer
    _, t0w = reset_timer()
    Tw = 0.01

    # collect error metrics
    count = 0
    rmse_sum = 0

    if type == "encoder" or type == "hebi" and backlash_compensation:
        #theta_init, _, _, _ = get_hebi_feedback(group, hebi_feedback)  
        #theta_init = np.array(theta_init)
        #c_init = np.array(c_R)
        #human_theta_d = initialize_backlash(c_init, m, theta_init)

        theta_init, _, _, _ = get_hebi_feedback(group, hebi_feedback)  
        human_theta_d = np.array(theta_init) - c_bl[1] # initialize backlash

    while True:
       count += 1

       t = loop_timer(t0w, Tw, print_loop_time=False)

       if type == "controller":
           pos_input, t_draw = controller_draw(joystick,pos_input,t_draw,gain)
           
       if type == "hebi":
           pos_input = calculate_hebi_position(group, hebi_feedback, offset)

       if type == "encoder":
           pos_input = calculate_encoder_position(arduino, offset)

       if type == "hebi" or type == "encoder":
            trajectory.coordinates(t)
            # print("trajectory.K", trajectory.K)
            K = 1*trajectory.K*1*np.matrix([[1, 0], [0, 1]])
            print("New K:", K)
            theta, omega, torque, hebi_limit_stop_flag = get_hebi_feedback(group, hebi_feedback)  
            omega_d, vel_d = calculate_velocity(theta, joystick, K)

            if not backlash_compensation:
                command.velocity = omega_d
                group.send_command(command)
            else:
                omega_f = user_input_filter(omega_d, cutoff_freq=user_cutoff_freq, T=Tw)
                human_theta_d += omega_f * Tw
                #theta_d = smooth_backlash_inverse(human_theta_d, omega_f, GPR_models=GPR_models, c_R=c_R, c_L=c_L, m=m, cutoff_freq=bl_cutoff_freq)
                theta_d = inverse_hammerstein(human_theta_d, omega_f, GPR_models=GPR_models, c=c_bl, K=K_bl, tau=tau_bl)
                e_d = P_controller(theta, theta_d, Kp)
                command.effort = e_d
                group.send_command(command)

       #if oneD:
       #    pos_input[1] = 500;

       draw_preview(animation_canvas, line, trajectory, preview_time, T, t)
       pos = target_ball.move(trajectory.screen_coordinates(t))
       target_ball.move(pos)

       input_ball.move(pos_input)
       animation_window.update()
       error = np.sqrt(np.sum(np.square(pos-pos_input)))
       rmse_sum += np.sum(np.square(pos-pos_input))
       if type == "controller":
           output += [[t, pos_input[0], pos_input[1], pos[0], pos[1], error]]
       else:
           output += [[t, pos_input[0], pos_input[1], pos[0], pos[1], vel_d[0,0], vel_d[0,1], error]]

       if i == 0:
           print("Ready to operate...")
           i = 1

       if t > T:
           rmse = np.sqrt(rmse_sum/count)
           save_data(output)
           output = np.array(output)
           print("Trajectory complete, saving data")

           velm1 = np.diff(output[:,1]*0.00037)/np.diff(output[:,0])
           velm2 = np.diff(output[:,2]*0.00037)/np.diff(output[:,0])

           velc1 = np.diff(output[:,3]*0.00037)/np.diff(output[:,0])
           velc2 = np.diff(output[:,4]*0.00037)/np.diff(output[:,0])

           plt.figure()
           plt.plot(output[:,0], output[:,1], label = "Actual Position x")
           plt.plot(output[:,0], output[:,2], label = "Actual Position y")
           plt.plot(output[:,0], output[:,3], label = "Desired Position x")
           plt.plot(output[:,0], output[:,4], label = "Desired Position y")
           plt.legend()
           plt.xlabel('Time [s]')
           plt.ylabel('Position [pixels]')
           plt.title('Position')

           plt.figure()
           if type == "controller":
               plt.plot(output[:,0], output[:,5])
           else:
               plt.plot(output[:,0], output[:,7])
           plt.xlabel('Time [s]')
           plt.ylabel('Position Error [pixels]')
           plt.title('Error (Total RMSE='+str(round(rmse))+' Pixels)')
           plt.legend()

           plt.figure()
           plt.plot(output[1:,0], velc1, 'k--', linewidth=1.0, label="Desired Velocity x")
           plt.plot(output[1:,0], -velc2, 'm--', linewidth=1.0, label="Desired Velocity y")
           plt.plot(output[:,0], output[:,5], 'b--', linewidth=1.5, label="User Desired Velocity x")
           plt.plot(output[:,0], output[:,6], 'r--', linewidth=1.5, label="User Desired Velocity y")
           plt.plot(output[1:,0], velm1, 'b', linewidth=1.5, label="Motor Velocity x")
           plt.plot(output[1:,0], -velm2, 'r', linewidth=1.5, label="Motor Velocity y")
           plt.xlabel('Time [s]')
           plt.ylabel('Position')
           plt.title('User Desired vs Actual Velocity')
           plt.legend()

           plt.show()

           break

       if keyboard.is_pressed('esc'):
           save_data(output)
           print("Trajectory interupted")
           #break
           while True and type is not "controller":
               command.velocity = np.nan*np.ones(2)
               command.effort = np.zeros(2)
               group.send_command(command)
           else:
               break

