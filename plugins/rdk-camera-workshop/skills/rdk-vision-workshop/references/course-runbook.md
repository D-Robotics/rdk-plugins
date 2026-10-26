# 四小时课程操作稿

本稿是执行方法，未预填任何实机成功。默认 X5＋已有适配 MIPI；GPU 与转换资源课前分配。

## 工具映射与缺口

课程计划：vision_course_plan / vision_course_stage，只读，不执行设备。
相机：读取本轮实际目录的 vision_workshop_runtime_status、camera probe/bringup、pipeline、新帧、ISP getter/apply/restore、AI Run、导出；工具逻辑名以实际 schema 为准，不能虚构参数。
主机/板卡：宿主实际提供的只读诊断、终端、文件、执行和浏览器工具。
训练/转换：配置好的GPU/兼容工具链主机，通过已有项目执行；没有远端主机则停止在资源缺口。
实时检测：配套官方/课程runner，静态图验证后接相机。相机插件与本课程插件不会安装这些环境。

## 时间与出口

0–15：任务、组别、板型、2–3类桌面目标、产物/模型来源。
15–40：连接、插件/adapter、保存实验、probe与已有驱动点亮、本次新图。
40–80：固定文字/中性/暗部场景、原始快照、真实范围/模式、有限候选、独立回读、至少三张每阶段A1/B/A2、选版。无收益可保留原值。80分钟停止深入ISP搜索。
80–100：10–20张不同条件新图，3–5张标注体验，合入基础数据。按采集片段划分train/val/test，不将相邻视频帧随机拆分。冻结数据/类别/哈希。
100–135：锁定版本YOLOv8n或已验收小模型，GPU短程微调约5轮（以预演耗时为准），保存run、日志、已完成checkpoint、验证预测。110–120休息包含在35分钟内，不另加。
135–165：部署ONNX（可能需适配输出头）、checker、代表性校准图、X5 Bayes-e工具链，保存编译日志、配置、分区与模型哈希。ONNX存在不能当BPU成功。
165–190：上传成套模型/labels/前后处理，静态图实际加载并验证目标结果。模型编译和板端runtime须兼容；CPU处理范围如实记录。
190–220：按交接稿验证检测流使用选定tuning，实际新帧→模型→解码→浏览器实时框，至少约定有界窗口，保存当前帧/结果来源。
220–230：固定模型/阈值对比原始与调优输入，说明漏检、误检、颜色/噪声/细节取舍；置信度变化不等于精度提升。
230–240：数据、权重、ONNX、BPU模型、tuning、日志、截图/流记录与scope/恢复状态一起交付，停止本组拥有的进程。

## 模型与超时

课前缓存权重、依赖、工具链镜像、校准图、独立测试集和同任务配套备用产物；并发组数按真实资源排练。不要现场安装CUDA、首次移植新Sensor或反复变模型架构。
第135分钟训练未完，选该run已完成可验证checkpoint；不存在则明确用课前版本。
第165分钟转换未完，后续演示用同架构/同类别/同输入与后处理的备用模型，本次转换仍未完成。
第190分钟静态推理失败保留日志，不挤占全部实时演示时间；备用模型来源明确。
不能将备用路径算作本组训练模型全链通过。

## 训练与导出约定

先读取现场已有课程配置和脚本，确认实际GPU主机、数据/模型版本、输入大小和预算，再执行。无文件时先生成可审查配置，不把模板说成已运行。
使用已审查训练器、固定导出分支与目标工具链；切换类别数量后核对输出shape、DFL/解码/NMS和标签顺序。预处理包括resize/letterbox、RGB/BGR/NV12、归一化、layout及坐标还原，校准与实际输入必须一致。自定义三类不可沿用80类标签或随意替换YOLOv5x的权重文件。

参考：
- https://docs.ultralytics.com/modes/train/
- https://docs.ultralytics.com/modes/export/
- https://github.com/D-Robotics/rdk_model_zoo
- https://developer.d-robotics.cc/rdk_x_doc/FAQ/toolchain
- https://developer.d-robotics.cc/rdk_x_doc/Basic_Application/pydev_demo_sample/RDK_X5/detection_sample
