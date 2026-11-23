# RDK Camera AI 1.5.7

在 RDK Studio 的扩展中心从 D-Robotics 官方市场源安装 RDK Camera AI，或下载 ZIP 后导入。选择器要求目录时，先解压并选择含 `plugin.json` 的文件夹。macOS 和 Windows 使用同一份插件。首次使用可查询插件版本与连接状态；相机服务连接信息由本工位提供。升级前请关闭旧课堂页。

- **日常相机调试**。在 Studio 助手说「用 RDK Camera AI 帮我点亮相机，读取当前 ISP」。按[相机操作技能](skills/rdk-camera-workshop/SKILL.md)执行。
- **180 分钟视觉 Workshop**。在 Studio 助手说「打开 180 分钟视觉 Workshop，继续我的工位」。通过 `vision_course_view` 打开本机工作台，按[课程操作稿](skills/rdk-vision-workshop/references/course-runbook.md)推进。
- **工位连接预检**。用 `vision_course_preflight` 或工作台的「运行连接预检」核对相机服务、X5 和实时画面。首次接入时从页面的「关联相机实验」绑定正确设备。
- **课堂 ISP**。保存原始版本，完成跟做和自主两轮 Gamma。每轮留下调前与调后实拍、独立参数回读和取舍。升级前关闭旧课堂页。讲师可现场缩短曝光，在相同增益下查看调前、调后实拍和恢复回读，也可切换五项实机归档。
- **拍照与三张基线**。在工位关联相机实验后打开「照片与三张基线图」，从图卡查看采集、归档与原件下载。也可通过 `vision_course_camera` 发起，使用 `vision_course_camera_status` 查看回执。渲染条件缺失时保留已归档的图并提示如何继续。

实际相机操作沿用相机适配器及原连接配置。课堂工作台保存相机证据，需要时可绑定当前相机实验。训练需本组 RoboGO 授权。提交、查询原 Run、PTQ 和板端验收按课程步骤完成。

相机连接器读取 `~/.config/rdk-camera-workshop/connection.json` 或 `RDK_CAMERA_WORKSHOP_CONFIG` 指定的私有文件。可运行 `node mcp/setup.mjs doctor` 核对连接。

Studio 1.5.8 需要显式登记两组 MCP。安装 Node.js 22 或更新版本，在解压后的插件目录（请保留该目录）用终端或 PowerShell 执行 `node mcp/studio-config.mjs`。在 Studio 的 MCP 配置中添加输出的两组服务，保留已有的其他服务，然后新建对话。该命令只输出本机配置。如果旧版 Studio 图形导入提示「审批签名配置缺失」，可从保留的解压目录生成配置，在 Studio 的 MCP 设置完成登记；需要图形导入时，请使用已修复审批配置的 Studio 版本。已有单独安装的视觉 Workshop 可接续到同名课程工具。已保存的课程进度可从工作台导入，按需重新附入实拍或回读附件。

工位、RoboGO 与板端归档配置见[课堂工作台配置](WORKSHOP.md)和[设备操作](device/README.md)。

学员在同一个课堂工作台里可以读取工位可写项目，单次调一个曝光、增益、对比度、锐度或白平衡数值。保留调前调后实拍、独立回读和取舍。真机逐项验收。
