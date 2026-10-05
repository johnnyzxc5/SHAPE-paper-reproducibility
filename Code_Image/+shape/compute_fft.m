function [amplitude,freq] = compute_fft(normalized_shape,cfg)
%COMPUTE_FFT M06 one-sided amplitude, exact N=10001 contract.
assert(isequal(size(normalized_shape),[6 cfg.n_time]));
N=cfg.n_time; n=(0:N-1)';
w=(0.5-0.5*cos(2*pi*n/(N-1)))'; % symmetric Hann without toolbox dependency
Y=fft(double(normalized_shape).*w,[],2);
A=abs(Y)/sum(w);
A(:,2:floor(N/2))=2*A(:,2:floor(N/2));
amplitude=single(A(:,1:1001));
freq=single((0:1000)*cfg.fs_hz/N);
end
