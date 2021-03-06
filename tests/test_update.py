import itertools

import numpy as np
from numpy.testing import assert_array_almost_equal
from sparseba.indices import Indices
from sparseba.core import SBA


def create_jacobian(mask, A, B):
    assert(A.shape[0] == B.shape[0])

    N = np.sum(mask)
    n_points, n_viewpoints = mask.shape
    n_pose_params = A.shape[2]
    n_point_params = B.shape[2]

    n_rows = 2 * N
    n_cols_a = n_pose_params * n_viewpoints
    n_cols_b = n_point_params * n_points
    JA = np.zeros((n_rows, n_cols_a))
    JB = np.zeros((n_rows, n_cols_b))

    # J' * J should be invertible
    # n_rows(J) >= n_cols(J)
    assert(n_rows >= n_cols_a + n_cols_b)

    viewpoint_indices = np.empty(N, dtype=np.int64)
    point_indices = np.empty(N, dtype=np.int64)

    index = 0
    for i, j in itertools.product(range(n_points), range(n_viewpoints)):
        if not mask[i, j]:
            continue

        viewpoint_indices[index] = j
        point_indices[index] = i

        row = index * 2

        col = j * n_pose_params
        JA[row:row+2, col:col+n_pose_params] = A[index]

        col = i * n_point_params
        JB[row:row+2, col:col+n_point_params] = B[index]

        index += 1

    sba = SBA(viewpoint_indices, point_indices)
    J = np.hstack((JA, JB))
    return sba, J


def create_weight_matrix(weights):
    N = weights.shape[0]
    W = np.zeros((N * 2, N * 2))
    for index in range(N):
        k = index * 2
        W[k:k+2, k:k+2] = weights[index]
    return W


def test_compute():
    # there shouldn't be an empty row / column
    # (empty means that all row elements / column elements = 0)
    # and it seems that at least two '1' elements must be
    # found per one row / column
    # mask.shape == (n_points, n_viewpoints)
    mask = np.array([
        [1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 0, 1, 1, 1, 0, 1, 1, 0],
        [1, 1, 1, 1, 1, 1, 0, 1, 0],
        [1, 0, 0, 1, 1, 1, 0, 1, 1],
        [0, 0, 1, 0, 0, 0, 0, 0, 1]
    ], dtype=np.bool)

    N = np.sum(mask)
    x_true = np.random.uniform(-9, 9, (N, 2))
    x_pred = np.random.uniform(-9, 9, (N, 2))
    A = np.random.random((N, 2, 4))
    B = np.random.random((N, 2, 3))

    n_pose_params = A.shape[2]
    n_viewpoints = mask.shape[1]
    size_A = n_pose_params * n_viewpoints

    sba, J = create_jacobian(mask, A, B)

    # unweighted Gauss-Newton
    H = np.dot(J.T, J)
    b = np.dot(J.T, (x_true - x_pred).flatten())
    delta = np.linalg.solve(H, b)
    delta_a, delta_b = sba.compute(x_true, x_pred, A, B, weights=None)
    assert_array_almost_equal(delta[:size_A], delta_a.flatten())
    assert_array_almost_equal(delta[size_A:], delta_b.flatten())

    # Levenberg-Marquardt
    mu = 0.5
    D = mu * np.identity(b.shape[0])
    delta = np.linalg.solve(H + D, b)

    delta_a, delta_b = sba.compute(x_true, x_pred, A, B, weights=None, mu=mu)
    assert_array_almost_equal(delta[:size_A], delta_a.flatten())
    assert_array_almost_equal(delta[size_A:], delta_b.flatten())

    # weigthed Gauss-Newton
    # weights have to be symmetric
    weights = np.array([np.dot(w.T, w) for w in np.random.random((N, 2, 2))])
    W = create_weight_matrix(weights)

    H = np.dot(np.dot(J.T, W), J)
    b = np.dot(np.dot(J.T, W), (x_true - x_pred).flatten())
    delta = np.linalg.solve(H, b)

    delta_a, delta_b = sba.compute(x_true, x_pred, A, B, weights)
    assert_array_almost_equal(delta[:size_A], delta_a.flatten())
    assert_array_almost_equal(delta[size_A:], delta_b.flatten())
