"""
evaluation
~~~~~~~~~~

Contains routines and classes to help with evaluation of predictions.
"""

import numpy as _np
from . import naive as _naive

def _top_slice_one_dim(risk, fraction):
    data = risk.compressed().copy()
    data.sort()
    N = len(data)
    n = int(_np.floor(N * fraction))
    n = min(max(0, n), N)
    if n == N:
        ret = _np.zeros(risk.shape) + 1
        return (ret * (~risk.mask)).astype(_np.bool)
    if n == 0:
        return _np.zeros(risk.shape, dtype=_np.bool)
    mask = (risk >= data[-n])
    mask = mask.data & (~risk.mask)
    have = _np.sum(mask)
    if have == n:
        return mask
    
    top = _np.ma.min(_np.ma.masked_where(~mask, risk))
    for i in range(len(risk)):
        if risk[i] == top:
            mask[i] = False
            have -= 1
            if have == n:
                return mask
    raise AssertionError()
    
def top_slice(risk, fraction):
    """Returns a boolean array of the same shape as `risk` where there are
    exactly `n` True entries.  If `risk` has `N` entries, `n` is the greatest
    integer less than or equal to `N * fraction`.  The returned cells are True
    for the `n` greatest cells in `risk`.  If there are ties, then returns the
    first (in the natual ordering) cells.

    The input array may be a "masked array" (see `numpy.ma`), in which case
    only the "valid" entries will be used in the computation.  The output is
    always a normal boolean array, where all invalid entries will not be
    selected.  For example, if half of the input array is masked, and
    `fraction==0.5`, then the returned array will have 1/4 of its entries as
    True.
    
    :param risk: Array of values.
    :param fraction: Between 0 and 1.

    :return: A boolean array, of the same shape as `risk`, where True indicates
      that cell is in the slice.
    """
    risk = _np.ma.asarray(risk)
    if len(risk.shape) == 1:
        return _top_slice_one_dim(risk, fraction)
    mask = _top_slice_one_dim(risk.ravel(), fraction)
    return _np.reshape(mask, risk.shape)


def hit_rates(grid_pred, timed_points, percentage_coverage):
    """Computes the "hit rate" for the given prediction for the passed
    collection of events.  For each percent, we top slice the that percentage
    of cells from the grid prediction, and compute the fraction of events which
    fall in those cells.

    :param grid_pred: An instance of :class:`GridPrediction` to give a
      prediction.
    :param timed_points: An instance of :class:`TimedPoints` from which to look
      at the :attr:`coords`.
    :param percentage_coverage: An iterable of percentage coverages to test.

    :return: A dictionary from percentage coverage to hit rate percentage.
    """
    risk = grid_pred.intensity_matrix
    out = dict()
    for coverage in percentage_coverage:
        covered = top_slice(risk, coverage / 100)
        count = 0
        for x, y in timed_points.coords.T:
            gx, gy = grid_pred.grid_coord(x, y)
            if covered[gy][gx]:
                count += 1
        out[coverage] = count / timed_points.coords.shape[1]
    return out

def maximum_hit_rate(grid, timed_points, percentage_coverage):
    """For the given collection of points, and given percentage coverages,
    compute the maximum possible hit rate: that is, if the coverage gives `n`
    grid cells, find the `n` cells with the most events in, and report the
    percentage of all events this is.

    :param grid: A :class:`BoundedGrid` defining the grid to use.
    :param timed_points: An instance of :class:`TimedPoints` from which to look
      at the :attr:`coords`.
    :param percentage_coverage: An iterable of percentage coverages to test.

    :return: A dictionary from percentage coverage to hit rate percentage.
    """
    pred = _naive.CountingGridKernel(grid.xsize, grid.ysize, grid.region())
    pred.data = timed_points
    risk = pred.predict()
    try:
        risk.mask_with(grid)
    except:
        # Oh well, couldn't do that
        pass
    return hit_rates(risk, timed_points, percentage_coverage)


class HitRateEvaluator():
    """Abstracts the task of 
    """