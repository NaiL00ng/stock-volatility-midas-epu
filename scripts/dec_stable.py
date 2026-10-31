"""Audited DEC solver and residual-only ablation; historical solver stays separate.

Variable projection eliminates linear coefficients. The bounded shape problem
uses analytic gradients and deterministic multistart; this is not a certificate
of a global optimum. No test outcomes enter a training objective or start choice.
"""
from itertools import product
import numpy as np
from scipy.optimize import minimize
from csi300_epu_final_from_oldcode import MidasResult

OPTIONS = dict(ftol=1e-14, gtol=1e-9, maxiter=2000, maxfun=10000, maxls=50)
STATIONARITY_TOL = 1e-6


def weights_and_jacobian(K, theta, family):
    if family == 'beta':
        x = np.arange(K, 0, -1, dtype=float) / (K + 1)
        basis = np.column_stack([np.log(x), np.log1p(-x)])
        log_raw = basis @ (np.asarray(theta) - 1)
        active = log_raw > np.log(1e-12)
        log_raw = np.maximum(log_raw, np.log(1e-12))
        basis = basis * active[:, None]
    elif family == 'expalmon':
        x = np.arange(K, 0, -1, dtype=float) / K
        basis = np.column_stack([x, x*x])
        log_raw = basis @ np.asarray(theta)
    else:
        raise ValueError('Unknown weight family')
    raw = np.exp(log_raw - np.max(log_raw))
    w = raw / raw.sum()
    jac = w[:, None] * (basis - w @ basis)
    return w, jac


def make_objective(y, lag_matrix, controls):
    y = np.asarray(y, dtype=float).reshape(-1)
    L = np.asarray(lag_matrix, dtype=float)
    C = np.ones((len(y), 1)) if controls is None else np.column_stack([np.ones(len(y)), controls])
    if not np.isfinite(np.column_stack([y, L, C])).all():
        raise ValueError('Nonfinite training inputs')
    # Orthogonal projection via SVD, avoiding normal-equation inversion.
    U, s, _ = np.linalg.svd(C, full_matrices=False)
    Q = U[:, s > s[0] * max(C.shape) * np.finfo(float).eps]
    u, R = y - Q @ (Q.T @ y), L - Q @ (Q.T @ L)

    def objective(theta, family):
        w, jac = weights_and_jacobian(L.shape[1], theta, family)
        z = R @ w
        zz = float(z @ z)
        if zz <= np.finfo(float).eps * max(float(np.sum(L*L)), 1):
            # EPU factor is effectively collinear with the controls.
            return float(u @ u / len(y)), np.zeros(2)
        gamma = float(z @ u / zz)
        r = u - gamma*z
        return float(r @ r / len(y)), -2*gamma/len(y) * (r @ R @ jac)
    return objective


def projected_gradient(theta, gradient, bounds):
    pg = np.asarray(gradient).copy()
    for j, (lo, hi) in enumerate(bounds):
        if (theta[j] <= lo + 1e-9 and pg[j] > 0) or (theta[j] >= hi - 1e-9 and pg[j] < 0):
            pg[j] = 0
    return float(np.max(np.abs(pg)))


def estimate_stable(y, lag_matrix, controls, weight_type='beta'):
    K = lag_matrix.shape[1]
    if weight_type == 'beta':
        bounds = [(0.05, 20.)]*2
        starts = list(product([.05,.5,1.5,5.,20.], [.05,.5,2.,5.,20.]))
    elif weight_type == 'expalmon':
        bounds = [(-5.,5.)]*2
        starts = [(-.2,-.02)] + list(product([-5.,-2.5,0.,2.5,5.], repeat=2))
    else:
        raise ValueError('Unknown family')
    objective = make_objective(y, lag_matrix, controls)
    fun = lambda x: objective(x, weight_type)
    candidates = []
    for start in starts:
        fit = minimize(fun, start, jac=True, bounds=bounds, method='L-BFGS-B', options=OPTIONS)
        val, grad = fun(fit.x)
        pg = projected_gradient(fit.x, grad, bounds)
        if pg > STATIONARITY_TOL:
            retry = minimize(fun, fit.x, jac=True, bounds=bounds, method='SLSQP',
                             options={'ftol':1e-14, 'maxiter':2000})
            v2, g2 = fun(retry.x)
            if np.isfinite(v2) and v2 <= val + 1e-12:
                fit, val, grad = retry, v2, g2
                pg = projected_gradient(fit.x, grad, bounds)
        candidates.append(dict(theta=fit.x.tolist(), mean_sse=float(val), projected_gradient_inf=pg,
                               success=bool(fit.success), message=str(fit.message), iterations=int(fit.nit)))
    best = min(candidates, key=lambda r: r['mean_sse'])
    if not np.isfinite(best['mean_sse']) or best['projected_gradient_inf'] > STATIONARITY_TOL:
        raise RuntimeError('Best multistart candidate failed stationarity; do not publish forecasts.')
    theta = np.array(best['theta'])
    w, _ = weights_and_jacobian(K, theta, weight_type)
    z = lag_matrix @ w
    X = np.column_stack([np.ones(len(y)), z]) if controls is None else np.column_stack([np.ones(len(y)), controls, z])
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ coef
    diagnostics = dict(solver='analytic_multistart_v1', **best, n_starts=len(starts),
                       gradient_tolerance_met=True, starts=candidates)
    return MidasResult(K=K, weight_type=weight_type, theta=theta, coef=coef,
                       sse=float(resid @ resid), optimizer=diagnostics)


def residual_only_predictions(df, config, base_col='yhat_xgb_market'):
    import pandas as pd
    residual = df.y - df[base_col]
    lagged = residual.shift(1)
    output = pd.Series(np.nan, index=df.index)
    coef = None
    for j in range(config.n_train + config.n_valid, len(df)):
        if (j - config.n_train - config.n_valid) % config.midas_refit_every == 0:
            y, lag = residual.iloc[:j].to_numpy(), lagged.iloc[:j].to_numpy()
            mask = np.isfinite(y) & np.isfinite(lag)
            coef = np.linalg.lstsq(np.column_stack([np.ones(mask.sum()), lag[mask]]), y[mask], rcond=None)[0]
        if coef is not None and np.isfinite(lagged.iloc[j]):
            output.iloc[j] = df[base_col].iloc[j] + coef[0] + coef[1]*lagged.iloc[j]
    return output
