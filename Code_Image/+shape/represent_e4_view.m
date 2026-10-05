function products = represent_e4_view(view,cfg)
%REPRESENT_E4_VIEW Materialize representations only when retention policy asks.
% The default E4 path keeps deterministic normalized temporal products and
% invokes this function on demand; no physical simulation is performed.
products=shape.cwt_representations(view.normalized,cfg);
[products.shape_fft_amplitude,products.fft_frequency_hz]=shape.compute_fft(view.normalized.shape,cfg);
end
