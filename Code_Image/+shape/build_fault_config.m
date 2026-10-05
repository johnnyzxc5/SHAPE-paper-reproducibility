function fault = build_fault_config(record,varargin)
%BUILD_FAULT_CONFIG Translate one manifest row into plant parameters.
instrument=false;
if nargin>1 && isstruct(varargin{1}) && isfield(varargin{1},'performance_instrumentation')
    instrument=logical(varargin{1}.performance_instrumentation);
end
name = string(record.fault_class);
fault = struct('Active',name~="Nominal",'LoE_joint',0,'Fric_joint',0,'Vib_joint',0, ...
 'LoE_time',double(record.t_fault),'Fric_time',double(record.t_fault), ...
 'Vib_time',double(record.t_fault),'LoE_sev',1-double(record.s_LoE), ...
 'Fric_delta_Fc',2.15*double(record.s_Friction),'Vib_amp',double(record.A_d), ...
 'Vib_freq',double(record.f_d),'Vib_phase',double(record.phi_d), ...
 'P0InstrumentationEnabled',instrument);
switch name
    case "LoE", fault.LoE_joint = 2;
    case "Friction", fault.Fric_joint = 2;
    case "Vibration", fault.Vib_joint = 2;
    case "Nominal"
    otherwise, error('shape:fault:Class','Unknown fault class %s.',name);
end
end
