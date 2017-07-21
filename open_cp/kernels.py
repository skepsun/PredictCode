"""
kernels
~~~~~~~

For us, a "kernel" is simply a non-normalised probability density function.
We use kernels extensively to represent (conditional) intensity functions in
point processes.

More formally, a kernel is any python object which is callable (e.g. a
function, or an instance of a class implementing `__call__`).  We follow the
e.g. scipy convention:

- A kernel expecting a one dimensional input may take a scalar as input,
  or a one-dimensional numpy array.  It should return, respectively, a scalar
  or a one-dimensional array of the same size.  For example::

    def gaussian(p):
        return np.exp(-p * p)

  Here we use `np.exp` to make sure that if `p` is an array, we handle it
  correctly.

- A kernel expecting a `k` dimensional input may take an array of shape `(k)`
  to represent a point, or an array of shape `(k,N)` to represent `N` points.
  The return should be, respectively, a scalar or an array of shape `(N)`.
  We follow this convention to allow e.g. the following::

   def x_y_sum(p):
       return p[0] + p[1]

  In the single-point case, `p[0]` is a scalar representing the x coordinate and
  `p[1]` a scalar representing the y coordinate.  In the multiple point case,
  `p[0]` is an array of all the x coordinates.
"""


import scipy.spatial as _spatial
import numpy as _np
import abc as _abc
import logging as _logging
import scipy.linalg as _linalg

_logger = _logging.getLogger(__name__)

class Kernel(metaclass=_abc.ABCMeta):
    """Abstract base class for classes implementing kernels.  You are not
    required to extend this class, but you should implement the interface.
    """
    @_abc.abstractmethod
    def __call__(self, points):
        """:param points: N coordinates in n dimensional space.  When n>1, the
          input should be an array of shape (n,N).
        
        :return: An array of length N giving the kernel intensity at each point.
        """
        pass
    
    @_abc.abstractmethod
    def set_scale(self, scale=1.0):
        """The output kernel should be multiplied by this value before being
        returned.
        """
        pass


class KernelEstimator(metaclass=_abc.ABCMeta):
    """Abstract base class for classes implementing kernel estimators.  You are
    not required to extend this class, but you should implement the interface.
    """
    @_abc.abstractmethod
    def __call__(self, coords):
        """:param coords: N coordinates in n dimensional space.  When n>1, the
          input should be an array of shape (n,N).
        
        :return: A kernel, probably an instance of Kernel.
        """
        pass


class GaussianKernel(Kernel):
    """A variable bandwidth gaussian kernel.  Each input Gaussian is an
    uncorrelated k-dimensional Gaussian.  These are summed to produce the
    kernel.
    
    :param means: Array of shape (k,M).  The centre of each Gaussian.
    :param variances: Array of shape (k,M).  The variances of each Gaussian.
    :param scale: The overall normalisation factor, defaults to 1.0.
    """
    def __init__(self, means, variances, scale=1.0):
#        if _np.any(_np.abs(variances) < 1e-8):
#            raise ValueError("Too small variance!")

        if len(means.shape) == 1:
            self.means = means[None, :]
            self.variances = variances[None, :]
        else:
            self.means = means
            self.variances = variances
        self.scale = scale
        
    def __call__(self, points):
        """For each point in `pts`: for each of i=1...M and each coord j=1...k
        we compute the Gaussian kernel centred on mean[i][j] with variance var[i][j],
        and then product over the j, sum over the i, and finally divide by M.
        """
        points = _np.asarray(points)
        if self.means.shape[0] == 1:
            if len(points.shape) == 0:
                # Scalar input
                pts = points[None, None]
            elif len(points.shape) == 1:
                pts = points[None, :]
            else:
                pts = points
        else:
            # k>1 so if points is 1D it's a single point
            if len(points.shape) == 1:
                pts = points[:, None]
            else:
                pts = points

        # x[:,i,j] = (pts[:,i] - mean[:,j])**2
        x = (pts[:,:,None] - self.means[:,None,:]) ** 2
        var_broad = self.variances[:,None,:] * 2.0
        x = _np.exp( - x / var_broad ) / _np.sqrt((_np.pi * var_broad))
        return_array = _np.mean(_np.product(x, axis=0), axis=1) * self.scale
        return return_array if pts.shape[1] > 1 else return_array[0]
        
    def set_scale(self, scale):
        self.scale = scale

class EpanechnikovKernel(Kernel):
    """A variable bandwidth gaussian kernel.  Each input Gaussian is an
    uncorrelated k-dimensional Gaussian.  These are summed to produce the
    kernel.
    
    :param means: Array of shape (k,M).  The centre of each Gaussian.
    :param variances: Array of shape (k,M).  The variances of each Gaussian.
    :param scale: The overall normalisation factor, defaults to 1.0.
    """
    def __init__(self, means, variances, scale=1.0):
#        if _np.any(_np.abs(variances) < 1e-8):
#            raise ValueError("Too small variance!")

        if len(means.shape) == 1:
            self.means = means[None, :]
            self.variances = variances[None, :]
        else:
            self.means = means
            self.variances = variances
        self.scale = scale
        
    def __call__(self, points):
        """For each point in `pts`: for each of i=1...M and each coord j=1...k
        we compute the Gaussian kernel centred on mean[i][j] with variance var[i][j],
        and then product over the j, sum over the i, and finally divide by M.
        """
        points = _np.asarray(points)
        if self.means.shape[0] == 1:
            if len(points.shape) == 0:
                # Scalar input
                pts = points[None, None]
            elif len(points.shape) == 1:
                pts = points[None, :]
            else:
                pts = points
        else:
            # k>1 so if points is 1D it's a single point
            if len(points.shape) == 1:
                pts = points[:, None]
            else:
                pts = points

        # x[:,i,j] = (pts[:,i] - mean[:,j])**2
        x = (pts[:,:,None] - self.means[:,None,:]) ** 2
        var_broad = self.variances[:,None,:]
        x = 3/4 * (1 - x / var_broad )
        x[x<0] = 0
        return_array = _np.mean(_np.product(x, axis=0), axis=1) * self.scale
        return return_array if pts.shape[1] > 1 else return_array[0]
        
    def set_scale(self, scale):
        self.scale = scale

def compute_kth_distance(coords, k=15):
    """Find the (Euclidean) distance to the `k` th nearest neighbour.

    :param coords: An array of shape (n,N) of N points in n dimensional space;
      if n=1 then input is an array of shape (N).
    :param k: The nearest neighbour to use, defaults to 15, if N is too small
      then uses N-1.
    
    :return: An array of shape (N) where the i-th entry is the distance from
      the i-th point to its k-th nearest neighbour."""
    points = _np.asarray(coords)
    k = min(k, points.shape[-1] - 1)

    out = _np.empty(points.shape[-1])
    # This naive algorithm is actually faster than using a KDTree!
    if len(points.shape) == 1:
        for i, pt in enumerate(points.T):
            dists_sq = (points - pt)**2
            dists_sq.sort()
            out[i] = dists_sq[k]
    else:
        for i, pt in enumerate(points.T):
            dists_sq = _np.sum((points - pt[:,None])**2, axis=0)
            dists_sq.sort()
            out[i] = dists_sq[k]
    return _np.sqrt(out)

def compute_normalised_kth_distance(coords, k=15):
    """Find the (Euclidean) distance to the `k` th nearest neighbour.
    The input data is first scaled so that each coordinate (independently) has
    unit sample variance.

    :param coords: An array of shape (n,N) of N points in n dimensional space;
      if n=1 then input is an array of shape (N).
    :param k: The nearest neighbour to use, defaults to 15, if N is too small
      then uses N-1.
    
    :return: An array of shape (N) where the i-th entry is the distance from
      the i-th point to its k-th nearest neighbour.
    """
    coords = _np.asarray(coords)
    if len(coords.shape) == 1:
        points = coords / _np.std(coords, ddof=1)
    else:
        points = coords / _np.std(coords, axis=1, ddof=1)[:, None]
    return compute_kth_distance(points, k)

def kth_nearest_neighbour_gaussian_kde(coords, k=15):
    """Estimate a kernel using variable bandwidth with a Gaussian kernel.
    The input data is scaled (independently in each coordinate) to have unit
    variance in each coordinate, and then the distance to the `k` th nearest
    neighbour is found.  The returned kernel is normalised, and is the sum
    of Gaussians centred on each data point, where the standard deviation for
    each coordinate is the distance for that point, multiplied by the standard
    deviation for that coordinate.

    See the Appendix of:
    Mohler et al, "Self-Exciting Point Process Modeling of Crime",
    Journal of the American Statistical Association, 2011
    DOI: 10.1198/jasa.2011.ap09546

    :param coords: An array of shape (n,N) of N points in n dimensional space;
      if n=1 then input is an array of shape (N).
    :param k: The nearest neighbour to use, defaults to 15, if N is too small
      then uses N-1.
    
    :return: A kernel object.
    """
    coords = _np.asarray(coords)
    means = coords.T

    if len(coords.shape) == 1:
        stds = _np.std(coords, ddof=1)
        if stds == 0:
            raise ValueError("0 standard deviation")
        points = coords / stds
    else:
        stds = _np.std(means, axis=0, ddof=1)
#        if _np.any(stds < 1e-8):
#            raise ValueError("0 standard deviation: {}".format(stds))
        points = coords / stds[:, None]
    distance_to_k = compute_kth_distance(points, k)
    # We have a problem if the `k`th neighbour is 0 distance
    mask = (distance_to_k == 0)
    if _np.any(mask):
        _logger.debug("Nearest neighbour distance is 0, so adjusting to 1")
        distance_to_k[mask] = 1.0
    
    var = _np.tensordot(distance_to_k, stds, axes=0) ** 2
    return GaussianKernel(means.T, var.T)

def marginal_knng(coords, coord_index=0, k=15):
    """Computes a one-dimensional marginal for the kernel which would be
    returned by :function kth_nearest_neighbour_gaussian_kde: Equivalent to,
    but much faster, than (numerically) integerating out all but one variable.
    
    :param coords: An array of shape (n,N) of N points in n dimensional space;
      if n=1 then input is an array of shape (N).
    :param coord_index: Which coordinate to return the marginal for; defaults
      to 0 so giving the first coordinate.
    :param k: The nearest neighbour to use, defaults to 15, if N is too small
      then uses N-1.
    
    :return: A one-dimensional kernel.
    """
    if len(coords.shape) == 1:
        raise ValueError("Input data is already one dimensional")
    distances = compute_normalised_kth_distance(coords, k)
    data = coords[coord_index]
    var = (_np.std(data, ddof=1) * distances) ** 2
    return GaussianKernel(data, var)


class KthNearestNeighbourGaussianKDE(KernelEstimator):
    """A :class:`KernelEstimator` which applies the algorithm given by
    :func:`kth_nearest_neighbour_gaussian_kde`

    :param k: The nearest neighbour to use, defaults to 15, if N is too small
      then uses N-1.
    """
    def __init__(self, k=15):
        self.k = k
        
    def __call__(self, coords):
        return kth_nearest_neighbour_gaussian_kde(coords, self.k)


class ReflectedKernel(Kernel):
    """A specialisation of :class:`Kernel` which is for where, along certain
    axes, we know that the data is concentrated on the positive interval
    [0, \infty].  We wrap an existing :class:`Kernel` instance, but reflect
    about 0 any estimated probability mass on the negative reals.

    :param delegate: The :class:`Kernel` instance to delegate to.
    :param reflected_axis: Which axis to reflect about.
    """
    def __init__(self, delegate, reflected_axis=0):
        self.delegate = delegate
        self.reflected_axis = reflected_axis

    def __call__(self, points):
        points = _np.asarray(points)
        if len(points.shape) <= 1:
            reflected = -points
        else:
            reflect = _np.zeros(points.shape[0]) + 1
            reflect[self.reflected_axis] = -1
            reflected = points * reflect[:,None]
        return self.delegate(points) + self.delegate(reflected)

    def set_scale(self, value):
        self.delegate.set_scale(value)


class ReflectedKernelEstimator(KernelEstimator):
    """Wraps an existing :class KernelEstimator: but reflects the estimated
    kernel about 0 in one axis.  See :class:`ReflectedKernel`

    :param estimator: The :class:`KernelEstimator` to delegate to.
    :param reflected_axis: Which axis to reflect about.
    """
    def __init__(self, estimator, reflected_axis=0):
        self.estimator = estimator
        self.reflected_axis = reflected_axis

    def __call__(self, points):
        kernel = self.estimator(points)
        return ReflectedKernel(kernel, self.reflected_axis)


class TimeSpaceFactorsEstimator(KernelEstimator):
    """A :class:`KernelEstimator` which applies a one-dimensional kernel
    estimator to the first (time) coordinate of the data, and another kernel
    estimator to the remaining (space) coordinates.

    :param time_estimator: A :class:`KernelEstimator` for the one-dimensional
      time data.
    :param space_estimator: A :class:`KernelEstimator` for the remaining
      coordinates.
    """
    def __init__(self, time_estimator, space_estimator):
        self.time_estimator = time_estimator
        self.space_estimator = space_estimator

    class Factors_Kernel(Kernel):
        def __init__(self, first, rest):
            self.first, self.rest = first, rest
            self.scale = 1.0

        def __call__(self, points):
            return self.time_kernel(points[0]) * self.space_kernel(points[1:])
        
        def set_scale(self, scale):
            self.scale = scale
            
        def time_kernel(self, points):
            """A one-dimensional, *normalised* kernel giving the time
            component of the overall kernel.
            """
            return self.first(points)
        
        def space_kernel(self, points):
            """The space component of the overall kernel, scaled appropriately.
            """
            return self.rest(points) * self.scale

    def __call__(self, coords):
        return self.Factors_Kernel(self.first(coords), self.rest(coords))

    def first(self, coords):
        """Find the kernel estimate for the first coordinate only.
        
        :param coords: All the coordinates; only the 1st coordinate will be
          used.
        
        :return: A one dimensional kernel.
        """
        return self.time_estimator(coords[0])

    def rest(self, coords):
        """Find the kernel estimate for the remaining (n-1) coordinates only.
        
        :param coords: All the coordinates; the 1st coordinate will be ignored.
        
        :return: A (n-1) dimensional kernel.
        """
        return self.space_estimator(coords[1:])


class KNNG1_NDFactors(TimeSpaceFactorsEstimator):
    """A :class:`KernelEstimator` which applies the
    :class:`KthNearestNeighbourGaussianKDE` to first coordinate with one value
    of k, and then to the remaining coordinates with another value of k, and
    combines the result.
    
    :param k_first: The nearest neighbour to use in the first coordinate,
      defaults to 100, if N is too small then uses N-1.
    :param k_rest: The nearest neighbour to use for the remaining coordinates,
      defaults to 15, if N is too small then uses N-1.
    """
    def __init__(self, k_first=100, k_rest=15):
        super().__init__(KthNearestNeighbourGaussianKDE(k_first), KthNearestNeighbourGaussianKDE(k_rest))


class GaussianBase():
    """Abstract base class which can perform a variety of Gaussian kernel
    tasks.  Any kernel estimation using this class is always of the form
    :math:`f(x) = \big(\sum_i w_i\big)^{-1}\frac{1}{|S|^{1/2}}\sum_{i=1}^N w_i
      frac{1}{h_i^n} K(h_i^{-2}(x_i-x)^T S^{-1} (x_i-x))`
    where `K(x) = (2\pi)^{-n/2} \exp(-x/2)` is the "quadratic" Gaussian kernel
    in `n` dimensions.  Here:
    
      - `S` is the covariance matrix (typically the actual sample covariance
        matrix of the input data, but this can be customised)
      - `h_i` is a sequence of "bandwidths".  By default these are constant,
        and set by a "rule of thumb", but they can vary.
      - `w_i` is a set of "weights", by default :math:`1/N` for all `i`.
    
    We do not support any form of cross-validation.
    
    The returned instance is a callable object which can be evaluated.
    
    With default settings, acts like the `scipy` Gaussian kde method.
    
    To change from the defaults, set one or more of the following attributes:
      
      - :attr:`covariance_matrix`
      - :attr:`bandwidth`
      - :attr:`weights`
    
    :param data: N coordinates in n dimensional space.  When n>1, the
          input should be an array of shape (n,N).
    """
    def __init__(self, data):
        data = _np.asarray(data)
        if len(data.shape) == 0:
            raise ValueError("Cannot be a single point")
        if len(data.shape) == 1:
            data = data[None,:]
        self._num_dims, self._num_points = data.shape
        self._data = data
        self._weights = None
        self._sqrt_det = 1

        self.bandwidth = "scott"
        self.covariance_matrix = None
        self.weights = None
        self.set_scale(1.0)
        
    def __call__(self, pts):
        pts = _np.asarray(pts)
        if len(pts.shape) == 1 and self.dimension > 1:
            pts = pts[:,None]
        else:
            pts = _np.atleast_2d(pts)
        if pts.shape[0] != self.dimension:
            raise ValueError("Data is {} dimensional but asked to evaluate on {} dimensional data".format(self.dimension, pts.shape[0]))
        x = self.data[:,:,None] - pts[:,None,:]
        x = _np.sum(x * _np.sum(self._cov_matrix_inv[:,:,None,None] * x[:,None,:,:], axis=0), axis=0)
        if len(self._bandwidth_2sq.shape) == 0:
            x = _np.exp(-x / self._bandwidth_2sq)
        else:
            x = _np.exp(-x / self._bandwidth_2sq[:,None])
            x = x / self._bandwidth_to_dim[:,None]
        if self.weights is not None:
            x = x * self.weights[:,None]
        return _np.sum(x, axis=0) / self._norm * self.scale
        
    def _update_norm(self):
        if self.weights is not None:
            norm = self._weight_sum
        else:
            norm = self.num_points
        norm *= self._sqrt_det
        if len(self._bandwidth_to_dim.shape) == 0:
            norm *= self._bandwidth_to_dim
        norm *= (2 * _np.pi) ** (self.dimension / 2)
        self._norm = norm
    
    @property
    def weights(self):
        """The sequence of weights, or `None` to indicate the default, a
        uniform weight."""
        return self._weights
    
    @weights.setter
    def weights(self, w):
        if w is None:
            self._weights = None
        else:
            w = _np.asarray(w)
            if len(w.shape) != 1 or w.shape[0] != self.num_points:
                raise ValueError("Need a one-dimensional array of the same length as the number of points.")
            self._weights = w
            self._weight_sum = _np.sum(w)
        self._update_norm()
        
    @property
    def bandwidth(self):
        """The bandwidth.  Set to a number, or one of the following strings:
          - "scott" for the Scott rule of thumb, `N**(-1./(n+4))`
          - "silverman" for Silverman’s Rule, `(N*(n+2)/4.)**(-1./(n+4))`
        Can also be a sequence for a "variable bandwidth".
        """
        return self._bandwidth
    
    @bandwidth.setter
    def bandwidth(self, band):
        if isinstance(band, str):
            if band == "scott":
                self.bandwidth = self.num_points ** (-1 / (4 + self.dimension))
            elif band == "silverman":
                self.bandwidth = (self.num_points * (self.dimension + 2) / 4.)**(-1. / (self.dimension + 4))
            else:
                raise ValueError("Unknown rule of thumb: '{}'".format(band))
            return

        band = _np.asarray(band)
        if len(band.shape) > 1 or (len(band.shape) == 1 and band.shape[0] != self.num_points):
            raise ValueError("Bandwidth must be a number, or a sequence the same length as the data.")
        self._bandwidth = band
        self._bandwidth_to_dim = band ** self.dimension
        self._bandwidth_2sq = 2 * band * band
        self._update_norm()

    @property
    def covariance_matrix(self):
        """The covariance matrix used in the kernel estimation.  (Note that
        actually it is the _inverse_ of this matrix which is used in the KDE).
        Set to `None` to use the default, which is the sample covariance.
        """
        return self._cov_matrix
    
    @covariance_matrix.setter
    def covariance_matrix(self, S):
        if S is None:
            S = _np.cov(self._data)
        S = _np.atleast_2d(_np.asarray(S))
        if S.shape[0] != S.shape[1]:
            raise ValueError("Must be a square matrix")
        if S.shape[0] != self.dimension:
            raise ValueError("Must be the same dimension as the data")
        self._cov_matrix = S
        self._cov_matrix_inv = _linalg.inv(S)
        self._sqrt_det = _np.sqrt(_linalg.det(self._cov_matrix))
        self._update_norm()

    @property
    def num_points(self):
        """The number of data points."""
        return self._num_points
    
    @property
    def dimension(self):
        """The number of dimensions."""
        return self._num_dims
    
    @property
    def data(self):
        """The data, an array of shape `(n,N)` where `n == self.dimension` and
        `N == self.num_points."""
        return self._data
    
    def set_scale(self, scale=1.0):
        self.scale = 1.0
    
    
class GaussianNearestNeighbour(GaussianBase):
    """A subclass of :class:`GaussianBase` which performs as    
    :func:`kth_nearest_neighbour_gaussian_kde`.  The :attr:`covariance_matrix`
    and :attr:`bandwidth` are set automatically, but you may sensibly alter
    :attr:`weights`.
    """
    def __init__(self, coords, k=15):
        super().__init__(coords)
        stds = _np.std(self.data, axis=1, ddof=1)
        points = self.data / stds[:, None]
        distance_to_k = compute_kth_distance(points, k)
        # We have a problem if the `k`th neighbour is 0 distance
        mask = (distance_to_k == 0)
        if _np.any(mask):
            _logger.debug("Nearest neighbour distance is 0, so adjusting to 1")
            distance_to_k[mask] = 1.0
        
        self.covariance_matrix = _np.diag(stds * stds)
        self.bandwidth = distance_to_k
