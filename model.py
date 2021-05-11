import numpy as np
import math
import control
from numpy.linalg import matrix_power


# Define trackings

def tracking_coordinates(t):
    y_1 = 16 * np.power(math.sin(t / 4), 3)
    y_2 = 13 * math.cos(t / 4) - 5 * math.cos(2 * t / 4) - 2 * math.cos(3 * t / 4) - math.cos(t)

    return y_1, y_2


# Matrix calculations

def _get_D(B, P, R):
    D = np.matmul(np.linalg.inv(R + np.matmul(np.matmul(np.transpose(B), P), B)), np.transpose(B))

    return D


def _get_H(B, D):
    H = np.matmul(B, D)

    return H


def _get_F(A, P, H):
    F = A - np.matmul(H, np.matmul(P, A))

    return F


def _get_K(F, P, H):
    K = np.linalg.inv(P) - np.matmul(F, np.matmul(np.linalg.inv(P), np.transpose(F))) - H

    return K


def compute_upper_bound(A, B, Q, R, OPT, lam, epsilon, X, Y, W, Z):
    bound_1 = 0
    bound_2 = 0
    P, _, _ = control.dare(A, B, Q, R)
    D = _get_D(B, P, R)
    H = _get_H(B, D)
    #
    # F = _get_F(A, P, H)
    # K = _get_K(F,P,H)
    # w, _ = np.linalg.eig(K)
    # lam_min = min(w)
    #
    # if lam_min > 0:
    #
    #     bound_1 = 1 + np.linalg.norm(H,2) * (lam*epsilon/OPT + (1-lam)/lam_min)
    #     bound_2 = 1 + np.linalg.norm(H,2) * (1/lam_min + lam*W/OPT)

    bound_1 = 1 + np.linalg.norm(H, 2) * (
                (lam ** 2) * (epsilon) / OPT + Z * ((1 - lam) ** 2) / OPT + Y * (1 - lam) * lam / OPT)
    bound_2 = 1 + np.linalg.norm(H, 2) * (Z / OPT + (lam ** 2) * W / (OPT) + X * (1 - lam) * lam / OPT)

    return min(bound_1, bound_2)


def generate_noise(mu, sigma, T, A):
    noise = np.zeros((T, np.shape(A)[0]))

    for t in range(T):
        noise[t] = np.random.normal(mu, sigma, np.shape(A)[0])
        noise[t] = 0.2 * np.random.binomial(10, sigma, np.shape(A)[0])

    return noise


def generate_w(mode, A, T):
    w = np.zeros((T, np.shape(A)[0]))

    if mode == 'Tracking':

        for t in range(T):
            y_1, y_2 = tracking_coordinates(t)
            y_3, y_4 = tracking_coordinates(t + 1)

            # Ground-true predictions
            w[t] = np.matmul(A, np.array([y_1, y_2, 0, 0])) - np.array([y_3, y_4, 0, 0])

    if mode == 'EV':

        for t in range(T):
            p = 0.1
            for i in range(np.shape(A)[0]):
                coin = np.random.binomial(1, p, 1)  # arriving rate 0.1
                if coin > 0:
                    w[i] = np.random.normal(10, 1, 1)
                else:
                    w[i] = 0

    return w


# A function for determining lambda
def _find_lam(t, w, estimated_w, P, F_list, H, s):
    prediction_perturbation = 0
    prediction_prediction = 0
    for s in range(t):
        left_1 = 0
        left_2 = 0
        right = 0
        for l in range(s, t):
            left_1 += np.matmul(np.matmul(np.transpose(estimated_w[l]), np.transpose(P)),
                                F_list[l - s])
            left_2 += np.matmul(np.matmul(np.transpose(w[l]), np.transpose(P)), F_list[l - s])
            right += np.transpose(
                np.matmul(np.matmul(np.transpose(estimated_w[l]), np.transpose(P)), F_list[l-s]))
        prediction_prediction += np.matmul(left_1, np.matmul(H, right))
        prediction_perturbation += np.matmul(left_2, np.matmul(H, right))

    if prediction_prediction != 0:
        lam_optimal = prediction_perturbation / prediction_prediction
    else:
        lam_optimal = 0.8

    return lam_optimal


def run_robot(T, A, B, Q, R, noise, lam, mode, P, D, H, F_list):
    # Initialize

    _myopic_x = np.zeros((T, np.shape(A)[0]))
    _optimal_x = np.zeros((T, np.shape(A)[0]))
    _online_x = np.zeros((T, np.shape(A)[0]))
    w = np.zeros((T, np.shape(A)[0]))
    estimated_w = np.zeros((T, np.shape(A)[0]))
    W = 0
    Z = 0
    Y = 0
    X = 0
    epsilon = 0

    # P, _, _ = control.dare(A, B, Q, R)
    # D = _get_D(B, P, R)
    # H = _get_H(B, D)
    # F = _get_F(A, P, H)
    # F_list = [np.linalg.matrix_power(F, i) for i in range(T)]

    myopic_ALG = 0
    online_ALG = 0
    OPT = 0

    for t in range(T):

        # Generate perturbations
        w = generate_w(mode, A, T)
        estimated_w = w + noise
        # Compute norms
        inner_epsilon = 0
        inner_W = 0
        inner_Z = 0
        for s in range(t, T):
            inner_epsilon += np.linalg.norm(F_list[s - t], 2) * np.linalg.norm(P, 2) * np.linalg.norm(noise[s])
            inner_W += np.linalg.norm(F_list[s - t], 2) * np.linalg.norm(P, 2) * np.linalg.norm(estimated_w[s])
            inner_Z += np.linalg.norm(F_list[s - t], 2) * np.linalg.norm(P, 2) * np.linalg.norm(w[s])
        epsilon += inner_epsilon ** 2
        W += inner_W ** 2
        Z += inner_Z ** 2
        Y += inner_epsilon * inner_Z
        X += inner_Z * inner_W

    for t in range(T):

        # Update actions

        _myopic_E = np.matmul(P, np.matmul(A, _myopic_x[t]))
        _online_E = np.matmul(P, np.matmul(A, _online_x[t]))
        _optimal_E = np.matmul(P, np.matmul(A, _optimal_x[t]))
        _myopic_G = 0
        _optimal_G = 0

        for s in range(t, T):
            _myopic_G += np.matmul(np.transpose(F_list[s - t]), np.matmul(P, estimated_w[s]))
            _optimal_G += np.matmul(np.transpose(F_list[s - t]), np.matmul(P, w[s]))

        # Myopic algorithm

        _myopic_u = -np.matmul(D, _myopic_E) - lam * np.matmul(D, _myopic_G)

        # Online algorithm (time-varying lambda)
        _FTL_lam = _find_lam(t, w, estimated_w, P, F_list, H, t)
        _online_u = -np.matmul(D, _online_E) - _FTL_lam * np.matmul(D, _myopic_G)

        # Omniscient algorithm
        _optimal_u = -np.matmul(D, _optimal_E) - np.matmul(D, _optimal_G)

        # Update states

        if t < T - 1:
            _myopic_x[t + 1] = np.matmul(A, _myopic_x[t]) + np.matmul(B, _myopic_u) + w[t]
            _online_x[t + 1] = np.matmul(A, _online_x[t]) + np.matmul(B, _online_u) + w[t]
            _optimal_x[t + 1] = np.matmul(A, _optimal_x[t]) + np.matmul(B, _optimal_u) + w[t]

        # Update costs

        if t < T - 1:

            myopic_ALG += np.matmul(np.transpose(_myopic_x[t]), np.matmul(Q, _myopic_x[t])) + np.matmul(
                np.transpose(_myopic_u), np.matmul(R, _myopic_u))
            online_ALG += np.matmul(np.transpose(_online_x[t]), np.matmul(Q, _online_x[t])) + np.matmul(
                np.transpose(_online_u), np.matmul(R, _online_u))
            OPT += np.matmul(np.transpose(_optimal_x[t]), np.matmul(Q, _optimal_x[t])) + np.matmul(
                np.transpose(_optimal_u), np.matmul(R, _optimal_u))

            # myopic_ALG += (x[t][0] ** 2) + (x[t][1] ** 2) + 0.01*(u[0] ** 2) + 0.01*(u[1] ** 2)
            # OPT += (_optimal_x[t][0] ** 2) + (_optimal_x[t][1] ** 2) + 0.01*(_optimal_u[0] ** 2) +  0.01* (_optimal_u[1] ** 2)
        else:
            online_ALG += np.matmul(np.transpose(_online_x[t]), np.matmul(P, _online_x[t]))
            myopic_ALG += np.matmul(np.transpose(_myopic_x[t]), np.matmul(P, _myopic_x[t]))
            OPT += np.matmul(np.transpose(_optimal_x[t]), np.matmul(P, _optimal_x[t]))

    # y = np.zeros((T, 2))
    #
    # for t in range(T):
    #     y_1, y_2 = tracking_coordinates(t)
    #     y[t] = [y_1, y_2]
    # plot_track(x,y)
    # plot_track(_optimal_x,y)
    # plot_trajectory(y)
    # plt.grid()
    # plt.show()

    print("Online Cost is")
    print(online_ALG)
    print("Myopic Cost is")
    print(myopic_ALG)
    print("Optimal Cost is")
    print(OPT)
    return epsilon, X, Y, W, Z, myopic_ALG, online_ALG, OPT
