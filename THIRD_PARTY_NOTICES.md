# Third-party notices and pending licensing

No project-wide LICENSE has been selected. Copying into this local assembly does not decide publication rights for SHAPE code, figures, robot parameter data or generated binaries.

`Code_Image/MATLAB/mr` derives from the NxRLab Modern Robotics library. The original local MATLAB README and function comments/attributions are retained. A missing license notice was recovered from the official upstream repository into `third_party/ModernRobotics/LICENSE` (MIT, copyright 2019 NxRLab); it applies to that upstream library, not automatically to this project. Retrieval, archive/notice hashes and file comparisons are recorded in `provenance/modern_robotics_upstream.json`. Of 47 local MATLAB files, 44 match the retrieved upstream text after newline/trailing-whitespace normalization. FKinBody.m, FKinSpace.m and InverseDynamics.m differ; the local scientific versions are preserved and their modifications/provenance require author review before distribution.

Official upstream: https://github.com/NxRLab/ModernRobotics . No MATLAB, Simulink, Coder, compiler or PyTorch distribution is bundled. The observer mexw64 binary came from the verified portable; publication and generated-code redistribution rights remain an author decision. External Python dependencies retain their respective upstream licenses; this repository does not relicense them.
