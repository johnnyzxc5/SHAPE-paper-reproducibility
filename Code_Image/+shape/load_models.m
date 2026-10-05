function models = load_models(code_dir)
%LOAD_MODELS Load robot matrices from the executable source tree.
if nargin<1, code_dir=fileparts(fileparts(mfilename('fullpath'))); end
nominal_path=fullfile(code_dir,'Kinova_MR_Nominal.mat');
dirty_path=fullfile(code_dir,'Kinova_MR_Sucia.mat');
nom=load(nominal_path);
suc=load(dirty_path);
models=struct('Mlist_nom',nom.Mlist,'Glist_nom',nom.Glist,'Slist_nom',nom.Slist, ...
 'Mlist_suc',suc.Mlist,'Glist_suc',suc.Glist,'Slist_suc',suc.Slist, ...
 'nominal_path',nominal_path,'dirty_path',dirty_path, ...
 'nominal_sha256',shape.sha256_file(nominal_path));
end
