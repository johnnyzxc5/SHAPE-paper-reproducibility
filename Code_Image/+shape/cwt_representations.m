function rep = cwt_representations(normalized,cfg)
%CWT_REPRESENTATIONS MATLAB amor CWT, COI neutralization, and physical rebin.
% Integrated CWT-1 (persistent filterbank) and REBIN-1 (precomputed invariant geometry).
persistent cached_fb cached_geom cached_cfg_key

signals=[normalized.shape;normalized.torque;normalized.gmo;normalized.energy];
n=size(signals,1); logp=zeros(n,cfg.output_size(1),cfg.output_size(2),'single');
mag=logp;

% Cache key for persistent filterbank and rebin geometry
cfg_key = [cfg.n_time, cfg.fs_hz, cfg.voices_per_octave, cfg.frequency_limits_hz, ...
           cfg.duration_s, cfg.output_size, cfg.coi_gamma];

rebuild = isempty(cached_fb) || isempty(cached_geom) || ...
          isempty(cached_cfg_key) || ~isequal(cached_cfg_key, cfg_key);

if rebuild
    cached_fb = cwtfilterbank('SignalLength', cfg.n_time, 'SamplingFrequency', cfg.fs_hz, ...
        'Wavelet', cfg.cwt_wavelet, 'VoicesPerOctave', cfg.voices_per_octave, ...
        'FrequencyLimits', cfg.frequency_limits_hz);
    
    [~, f_sample, coi_sample] = wt(cached_fb, signals(1,:));
    src_x = double(f_sample(:));
    src_y = double(linspace(0, cfg.duration_s, cfg.n_time)');
    out_size = cfg.output_size;
    gamma = cfg.coi_gamma;
    
    flip_x = (src_x(1) > src_x(end));
    if flip_x, src_x = flipud(src_x); end
    
    xe = zeros(numel(src_x)+1, 1); xe(2:end-1) = 0.5*(src_x(1:end-1)+src_x(2:end));
    xe(1) = src_x(1)-(xe(2)-src_x(1)); xe(end) = src_x(end)+(src_x(end)-xe(end-1));
    
    ye = zeros(numel(src_y)+1, 1); ye(2:end-1) = 0.5*(src_y(1:end-1)+src_y(2:end));
    ye(1) = src_y(1)-(ye(2)-src_y(1)); ye(end) = src_y(end)+(src_y(end)-ye(end-1));
    
    xe([1 end]) = src_x([1 end]); ye([1 end]) = src_y([1 end]);
    dxe = linspace(xe(1), xe(end), out_size(1)+1); dye = linspace(ye(1), ye(end), out_size(2)+1);
    Wx = max(0, min(dxe(2:end)', xe(2:end)') - max(dxe(1:end-1)', xe(1:end-1)'));
    Wy = max(0, min(dye(2:end)', ye(2:end)') - max(dye(1:end-1)', ye(1:end-1)'));
    area = (diff(dxe(:)) * diff(dye(:))');
    
    coi_row = coi_sample(:)';
    valid_native = double(src_x >= coi_row);
    coverage = (Wx * valid_native * Wy') ./ area;
    valid = coverage >= gamma;
    denom = max(Wx * valid_native * Wy', eps);
    
    cached_geom = struct(...
        'Wx', Wx, 'Wy_t', Wy', 'valid_native', valid_native, ...
        'denom', denom, 'valid', valid, ...
        'freq_out', 0.5*(dxe(1:end-1)+dxe(2:end)), ...
        'time_out', 0.5*(dye(1:end-1)+dye(2:end)), ...
        'flip_x', flip_x ...
    );
    cached_cfg_key = cfg_key;
end

fb = cached_fb;
geom = cached_geom;
Wx = geom.Wx;
Wy_t = geom.Wy_t;
valid_native = geom.valid_native;
denom = geom.denom;
valid = geom.valid;
flip_x = geom.flip_x;

for c=1:n
    x=signals(c,:); if cfg.use_gpu, x=gpuArray(x); end
    wt_c = wt(fb, x);
    wt_c = gather(wt_c);
    if flip_x, wt_c = flipud(wt_c); end
    
    val_p = double(abs(wt_c).^2);
    weighted_p = Wx * (val_p .* valid_native) * Wy_t;
    p = weighted_p ./ denom;
    p(~valid) = 0;
    
    val_m = double(abs(wt_c));
    weighted_m = Wx * (val_m .* valid_native) * Wy_t;
    m = weighted_m ./ denom;
    m(~valid) = 0;
    
    z = max(10*log10(p + cfg.power_epsilon), cfg.log_floor_db);
    z(~valid) = cfg.log_floor_db;
    
    logp(c,:,:) = single(z);
    mag(c,:,:) = single(m);
end

rep = struct('shape_log',logp(1:6,:,:),'torque_log',logp(7:12,:,:), ...
 'gmo_log',logp(13:18,:,:),'energy_log',logp(19,:,:), ...
 'shape_magnitude',mag(1:6,:,:),'torque_magnitude',mag(7:12,:,:), ...
 'gmo_magnitude',mag(13:18,:,:),'energy_magnitude',mag(19,:,:), ...
 'freq_hz',single(geom.freq_out),'time_s',single(geom.time_out),'coi_valid_mask',logical(valid));
end

