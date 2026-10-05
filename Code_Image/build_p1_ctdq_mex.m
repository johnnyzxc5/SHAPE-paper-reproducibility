function receipt = build_p1_ctdq_mex(force_rebuild)
%BUILD_P1_CTDQ_MEX Reproducibly build the batched finite-difference GOLD MEX.
if nargin<1, force_rebuild=false; end
code_dir=fileparts(mfilename('fullpath'));
build_dir=fullfile(code_dir,'generated','p1_ctdq_mex');
if ~isfolder(build_dir), mkdir(build_dir); end
artifact=fullfile(build_dir,['ctdq_finite_difference_batch_mex.' mexext]);
source=fullfile(code_dir,'ctdq_finite_difference_batch_mex_source.m');
compiler=mex.getCompilerConfigurations('C++','Selected');
if isempty(compiler), error('shape:p1:NoCompiler','No selected C++ compiler.'); end
build_time_s=0;
if force_rebuild || ~isfile(artifact)
    args={coder.typeof(0,[6 Inf],[false true]),coder.typeof(0,[6 Inf],[false true]), ...
        zeros(4,4,7),zeros(6,6,6),zeros(6,6)};
    x=tic;
    output_base=fullfile(build_dir,'ctdq_finite_difference_batch_mex');
    codegen('-config:mex','ctdq_finite_difference_batch_mex_source','-args',args, ...
        '-o',output_base,'-d',build_dir,'-report');
    build_time_s=toc(x);
end
assert(isfile(artifact),'shape:p1:MissingMexArtifact');
receipt=struct('source',source,'source_sha256',shape.sha256_file(source), ...
    'artifact',artifact,'artifact_sha256',shape.sha256_file(artifact), ...
    'build_dir',build_dir,'build_time_s',build_time_s, ...
    'matlab_version',version,'matlab_coder_version',local_coder_version(), ...
    'target_architecture',computer('arch'),'mex_extension',mexext, ...
    'generated_code_source_sha256',local_generated_hash(build_dir), ...
    'compiler_name',compiler.Name,'compiler_version',compiler.Version, ...
    'command',["codegen('-config:mex','ctdq_finite_difference_batch_mex_source'," ...
        "'-args',{6xN double,6xN double,4x4x7 double,6x6x6 double,6x6 double}," ...
        "'-o',fullfile(build_dir,'ctdq_finite_difference_batch_mex')," ...
        "'-d',build_dir,'-report')"]);
end

function value=local_coder_version()
v=ver; names=string({v.Name}); k=find(names=="MATLAB Coder",1);
if isempty(k), value='UNAVAILABLE'; else, value=v(k).Version; end
end

function value=local_generated_hash(build_dir)
files=[dir(fullfile(build_dir,'**','*.c'));dir(fullfile(build_dir,'**','*.h')); ...
    dir(fullfile(build_dir,'**','*.cpp'));dir(fullfile(build_dir,'**','*.hpp'))];
tokens=strings(numel(files),1);
for k=1:numel(files)
    path=fullfile(files(k).folder,files(k).name);
    rel=erase(path,[build_dir filesep]);
    tokens(k)=string(rel)+":"+string(shape.sha256_file(path));
end
tokens=sort(tokens);
tmp=[tempname '.txt']; fid=fopen(tmp,'w'); assert(fid>=0); cleanup=onCleanup(@() fclose(fid));
fprintf(fid,'%s\n',tokens); clear cleanup; value=shape.sha256_file(tmp); delete(tmp);
end
