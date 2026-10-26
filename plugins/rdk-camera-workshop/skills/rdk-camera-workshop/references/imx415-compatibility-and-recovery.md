# X5 / IMX415 兼容性与失败恢复

## 截至2026-10-16的最新实机结论与阅读入口

先读[最新实机结果与R3](#2026-10-16-新原sdk基线固定aeawb的cproc负结果及r3)和[源码审计及下一步](#2026-10-16-只读sensor源码审计收口与下一步)；下方早期`documentation_preflight_only`等表述保留当时的历史范围。
原SDK裸start实机采图及已归档boot的稀疏AE/AWB current-value往返已通过；资格只绑定该boot/SDK/profile/私有路径与采样时点。最新c983复测已通过严格连续窗口及AE/AWB保留当前数值的模式往返，共4次中性setter，CORE4/原管线完整恢复通过；资格仅绑定该boot/runtime/native/Sensor/RX tuple，不代表数值调优或画质通过。详见[本次模式边界](#2026-10-16-c983模式复测通过的严格边界)。 随后已完成[同时固定AE/AWB及恢复](#2026-10-16-c983联合固定曝光与白平衡实机通过)，仍未取得画质收益。

以下阶段记录保留当时状态；旧段中的尚未执行/0setter等不代表当前。当前结论以上方入口和末段收口为准。
EE down64、both96和固定AE/AWB的CPROC三组候选均确认恢复原配置，但没有被接受为通用画质收益，尚无最佳ISP配置。
EE MANUAL中性请求在SDK setter阶段失败，仍未取得资格；Bayer RAW、完整active效果库字节身份、物理INCK和时序正确性也未认证。
这是私有Codex监督的工程链路，不能当作已配置的平台后台Agent Run。R3虽已安装为私有运行时，不能继承旧boot/路径资格；
使用新路径须重新完成原SDK采图参考与实际模式往返。


用于版本选择、点亮前提、ISP 调优和失败后的下一步判断。来源核查截至 2026-10-16；
下面的实机结果属于已保存的本轮历史证据，不是实时设备状态，也不是可自动重放的操作清单。
任务只要求查资料时保持只读；安装插件或读取文档不授权升级、烧录、重启或调参。

## 镜像、ROS 与 SDK 分别核对

用户提供的七页《RDK X5 驱动 IMX415 摄像头教程》PDF，SHA-256 为
`ffb3b559879673f6add256d51bcc7f43eeeace54d122c695c3b7bbdcbededd9c`。
结合《IMX415_主板兼容性说明（必看）.xlsx》的截图，按以下边界使用：

| 来源 | 已确认的条件 | 决策边界 |
| --- | --- | --- |
| PDF 第1、3、4页 | 厂商 ROS 直接支持路线要求 RDK X5 镜像 ≥3.5.0、TROS Humble，`tros-humble-mipi-cam` 和 `tros-humble-hobot-stereonet` 均 ≥2.4.1 | 这是该厂商指南的组合条件，不证明所有旧版原生采集都不可能出图，也不证明当前安装已满足条件。 |
| PDF 第4页第4节 | 旧版 **ROS 镜像**有专属的依赖、系统及 miniboot 升级说明 | 先核对镜像来源与适用说明；不将步骤推广到任意旧镜像，不自动执行更新。 |
| 兼容性截图 | X5 默认 I²C 地址 `0x1a`；≥3.5.0 标为可直接使用；两个 <3.5.0 分支分别标为厂商提供适配、无法驱动且不支持命令升级 | 截图可见单元格没有标出两个旧分支各自的镜像类别。不能擅自分别贴上“ROS”或“大模型镜像”标签。 |
| PDF 第3、5页 | 指南复用 TROS/BSP 的 `mipi_cam`，并通过 `hobot_codec`、`websocket` 展示；没有提供独立 Linux 内核模块 | 不是一个通用于任意 BSP 的驱动安装包；不能套用截图中树莓派的 `.ko`/设备树地址修改路线。 |

只知道系统为 3.1.1 时，只能确认低于上述直接支持门槛；是否可按旧 ROS 说明升级仍需镜像来源证据。
RDKOS 3.5.0 与 SDK 文档 2.0.0 是不同版本标识，不能相互推导。
升级后也须重新核对实际 headers、共享库、VP 布局和运行时 ABI，而不是把升级当作兼容验收。

### 2026-10-16 重读附件：示例照片的时钟线索

用户再次提供的 `rdk-x5-imx415(1).pdf` 仍为上述相同 SHA-256 的七页教程，没有新增版本。
逐页渲染及提取内嵌原图后，第3页 IR-CUT 拨码开关旁的金属器件可辨标记为 `24.000`，
作为**教程示例模组可能使用24MHz振荡器**的硬件线索记录。
文档没有说明示例 PCB 与当前模组的版本对应、INCK 走线或测量结果；
不能据该照片确认当前实物的 INCK，也不能把此前约30fps的完整时序候选改写成物理时钟已认证。
正文没有给出 INCK 配置表、PLL 寄存器、lane 保证或 ISP tuning 参数。

第4页既有的系统/ROS包要求、旧 ROS 镜像的 miniboot 升级说明和第3页 IR-CUT 说明仍按上表使用。
已有升级后实测为 OS3.5.0、mipi-cam2.5.2/stereonet2.5.5；该附件未提供再次升级或刷新 miniboot 的新增依据。
ROS `/image`→JPEG→WebSocket 只说明预览链，不证明 Bayer RAW；
风扇 I²C5/`0x0d` 也不能代替 Sensor 控制总线/地址或时钟证据。

## 接口、模式与“检测到”的含义

官方 X5 板卡资料给出的接口映射如下。用相对以太网口的位置和板卡标识定位，
“上方接口”会随板卡摆放改变，不能单独决定端口。

| 板端位置 | CSI host | I²C 总线 | reset GPIO |
| --- | --- | --- | --- |
| 靠近以太网口 | 0 | 6 | 353 |
| 远离以太网口 | 2 | 4 | 351 |

这些映射来自官方板卡资料，不来自厂商 PDF；PDF 第2页只展示模组排线照片。
核对 22pin 同向排线、触点方向和锁扣；更换排线或接口前先断电。
不要把 SDK EVB 的 GPIO/总线表套到 RDK X5。

官方 VP 提供 IMX415 的 3840×2160、linear RAW10、30 fps、`0x1a` 的 2-lane 与 4-lane profile。
这证明存在两个软件配置，不证明当前模组、排线及端口都支持两种模式，也不证明实际帧率达标。
厂商 PDF 和截图没有给出 lane 或原生分辨率，必须另核对实物及所选官方配置。
CSI host 编号只用于 VIN 的 `mipi_rx`；profile 的 `rx_attr.phy` 是 DPHY/CPHY 类型，不能写成 host 2。

旧版 `libsrcampy.open_cam` 的 `video_index` 选择板卡配置中的 camera 条目，不直接等于 host 编号。
其 `raw_height/raw_width` 是原生 Sensor 模式筛选条件，输出缩放尺寸是另一组参数；
用 1920×1080 筛选原生 3840×2160 的 IMX415 可能排除已检测到的模式。
Python 接口没有显式 Sensor 名称/lane 参数；需要固定模式时使用匹配 SDK 的官方配置与受控 adapter，
不猜 profile 索引，也不因自动检测列出两种模式就宣称两者均通过。

I²C ACK 只证明某地址有响应；匹配 chip ID 也不证明 CSI 有数据、ISP 有输出或帧可用。
`No camera sensor found` 是当次探测/过滤失败结果，不能直接等同于相机未连接或损坏。
探测读失败被显示为 `00` 时，不能把它当作真实 Sensor ID。
`mipi mclk is not configed` 表示未配置 SoC 输出 MCLK，不是实际时钟测量；
外部晶振模组可能正常采集，不能只据该提示改设备树或认定致命。

### INCK、配置时钟与物理测量分开

[Sony官方产品资料](https://www.sony-semicon.com/files/62/pdf/p-12_IMX415-AAQR_AAMR_Flyer.pdf)
列出24、27、37.125、72、74.25MHz五种输入主时钟。
[Sony原始datasheet的Khadas镜像](https://dl.khadas.com/products/add-ons/cameras/imx415/datasheet/imx415-datasheet.pdf)
第16页给出的允许输入范围为标称值的−4%～+2%，不是晶振的典型精度；
第13页 Sensor 引脚名为 INCK/M11，不能假定存在可测的 Sensor XIN/XOUT。
物理测量应先由模组原理图确认 INCK 测试点或振荡器输出。

[Linux v6.12 IMX415驱动](https://github.com/torvalds/linux/blob/v6.12/drivers/media/i2c/imx415.c)
按 clock framework 提供的预期输入频率与 lane rate 匹配完整寄存器组合，不测量实际 INCK。
寄存器回读证明写入的配置；“常见24MHz”、照片、配置声明与实际测量分别保存。
不要将五种频率当成可独立盲试的开关，完整模式还包含 lane 数、PLL、HMAX/VMAX及接收端。

本轮对应 X5 3.5.0 MIPI 源码对 `mclk=2..24` 忽略，频率设置接口单位为10kHz；
旧配置中的 `mclk:24` 不能解读为已经输出24MHz。
当前启动的只读刷新为 `cfg_clock:csi2_cfg(24000000)`、`snr_clock:null(0)`，
`snrclk:none/noused/freq:0`，该 host 的 DT 未声明 `snrclk-idx`/`clocks` 等对应属性。
`csi2_cfg` 是接收端配置时钟，不是 Sensor INCK；这些状态只说明该 host 未托管 Sensor 时钟，
不能证明模组未供时钟或确认其外部振荡器频率。
当前结论仍为：37.125MHz假设配套的完整时序候选实测恢复约30fps，物理 INCK 未测得。

## 光学条件与画质判断

模组资料标明手动对焦。存在 AF/AFM 软件 API 不等于这颗模组有可控对焦马达；
没有已实现的软件原子能力时，由实际操作员调整焦点并确认目标距离，再采新帧比较。
模糊可能与焦点、距离、运动、曝光或 ISP 有关，不能只看一张图就确诊物理失焦。
数字锐化不能恢复已经丢失的细节。

PDF 第3页说明 IR-CUT OFF 用于常规可见光色彩，ON 允许红外且可能偏红。
记录实际开关状态、场景照明与目标；不要用白平衡补偿未经确认的 IR-CUT 状态。
比较同尺寸、同颜色转换的新帧中固定的文字、物体边缘和纹理，明确人物移动等局限。
同时检查可辨细节、噪声、光晕、曝光和颜色；全局方差、Laplacian、颗粒增加或单纯变暗都不能证明清晰度改善。

## 本轮历史证据与停止条件

| 保存证据 | 可以说明什么 | 不能说明什么 |
| --- | --- | --- |
| 2026-10-14 官方 `libsrcampy` 曾连续读取80帧并保存可辨识现场图像；Sensor 模式为3840×2160，输出1280×720 | 当时官方短采集链路曾可用 | 不证明当前仍出图、稳定实际帧率、4-lane、平台原生 v2、Bayer RAW、ISP 恢复或画质通过。 |
| 2026-10-14 19:01，单次恢复官方相机服务后完成90次成功取图并保存现场图像，随后正常关闭 | 当时官方链路有一次故障恢复证据 | 未独立验证每帧 ID/时间戳；不证明参数恢复、临时桥或热切换稳定性，也不授权平台自动重启服务。 |
| 已核对的3.1.1环境使用旧 multimedia/dev SDK；缺少本原生 v2 所需的新版 CPROC、EE、2DNR/3DNR typed 接口，CPROC 使用旧 API | 此 SDK 不能仅凭官方出图就视为兼容当前 v2 adapter | 不能伪造类型、替代 setter 或将另一版本 SDK 的字段直接写入；临时诊断桥不属于插件适配器。 |
| 2026-10-15 新 boot 后的保存日志出现 MIPI PHY stop-state 等待失败、开流 `-36`，并有关闭 `-37` | 当次流生命周期失败，不能继续当作已点亮或已恢复 | 数字报错本身未证明版本、lane、时钟或硬件损坏中的唯一根因；PDF 没有解释这些错误码。 |
| 2026-10-15 未加载临时 preload 桥的官方程序同样失败；2-lane、4-lane 均0帧；当日重启一次相机服务仍未恢复 | 失败不只发生在加载临时桥的路径；当天这次重启没有恢复证据，与前一天单次成功分别记录 | 不证明桥绝无影响、两种 lane 均不受支持、设备永久故障或需要反复重启；也不能用前一天成功覆盖当天失败。 |

失败发生后停止 ISP 优化，保留原始日志、版本、profile、开关状态与帧计数；
先解决受支持的镜像/驱动组合和稳定开流，再评价光学条件及 ISP。
更低系统版本是排查线索，不能宣称已证实为 `-36` 的唯一原因。
没有新的原因证据或明确受控方案时，不重复重放失败 scene，不自动重启设备或循环切换 lane。

## typed controls 与恢复门禁

1. 先读取当前能力和只读 probe，分别识别 SDK 缺口、待开流与实际取帧失败。
   X5 typed controls/getter 依赖已成功创建的真实 pipeline；开流失败后不硬试 getter/setter，
   不以临时桥或热切 scene 绕过 SDK 不兼容。
2. 成功开流并归档本次有效新帧后，再用真实 getter 保存原始配置、版本与哈希。
   只有支持、可写且 active 的字段进入调参；实际运行时模式与范围不能用配置声明代替。
3. 写后用独立 getter 核对实际值，并取得有效新帧及对应 tuningHash。
   场景切换函数返回成功、请求值回显或旧队列图像都不能证明 ISP 已应用或流仍可用。
4. 写入异常、取帧失败或清理不完整时，保留 `cleanupRequired:true`、
   `writeOutcome:'unconfirmed'` 或相应恢复错误；不能因重启 daemon、Run completed 或配置哈希匹配就清除。
   新 AI Run 必须被真实 recovery fence 阻止，先显式停止/清理，再恢复、getter 回读和取得新帧。
   失败恢复只尝试已授权的受控路径；不在 catch 中再次自动恢复或重复重放失败 scene。
5. 分开报告配置恢复与流验证。`final.restored` 只确认配置；
   `streamVerification:'verified'` 需要恢复后的新帧、有效归档及匹配哈希，
   `'failed'` 阻止新调试，历史缺少此字段按 `'unverified'` 展示，不能伪装已验证或一概阻断所有历史实验。

readiness 的保存观察不是实时探测。无 AI 历史也可能有清理/写入未确认的 probe 记录；
提示用户重新检查连接以取得当前 probe，并按实际清理/恢复结果更新状态，不能永久沿用旧失败记录。
普通 `streaming:false` 仅表示停止，不单独判成未恢复。
报告 SDK 不兼容、取帧失败、清理待完成或恢复待确认的具体原因和下一步，不输出“恢复成功”占位文本。

## 2026-10-15 后续升级与实机复验

以下追加旧案例之后的观察；不覆盖前述失败，也不表示当前设备永远在线。
升级后的实测组合为 RDKOS 3.5.0、multimedia 3.0.5、multimedia-dev 3.0.4、
spdev 3.0.9。原生 ABI 2 用实际 headers、库和 VP profile 编译/链接/加载，
backend/modules/replay 隔离测试通过；这些是本组合的软件证据，不自动延伸到其他 SDK。

后续原接口恢复控制应答并取得 3840×2160 NV12 新帧。2-lane 的取帧 -43 与同次
MIPI CRC/PHY fatal、SIF 尺寸错误同时出现；这是关联，不是所有 -43 的唯一根因。
当前安装 HBN 头文件中 43 为 NODE_DEQUE_ERROR，返回阶段仍须实际诊断。
attach 的 -207 在对应相机头文件中为 HB_CAM_I2C_WRITE_FAIL；
它属于控制访问失败，不能与旧 -36/-37 或取帧 -43 合并解释。

使用该 SDK 完整官方 4-lane profile、CSI host2 后，有一次 90 秒/299 次成功取图，
没有新增 CRC/PHY 错误，后续一次预览取得 407 张图且 0 次恢复、正常关闭。
这是有界证据。另一次预览前约 78 秒可用、后来在 543 帧附近失败；
0 setter 的只读预览也报过 -43。不能据此承诺永久稳定或将 profile 标注的 30fps 当实测率。
帧号/SDK 时间/主机时间的来源和分组需保存；帧率与参考时钟不符先排查，不凭比例猜定晶振。
控制访问与开流均失败时，ISP 调参停止；完整断电后重新确认 chip/profile/新帧，
才可记录一次受控恢复，不据此默认反复断电或重启服务。

公开 getter 曾有 hdr_exposure/autofocus/rgbir 返回 -35；本安装版本中为 GET_CONTROL_FAIL，
不是 NOT_SUPPORT。module_control.version 则在 SDK 成功返回时出现越界漂移，
必须保留语义异常证据，不能归零或伪造非零 SDK 错误。
配置 scope 从可读模块进一步收窄时参与 layoutHash，原始库归档与公开模块范围分开。
实际完成核心 exposure/awb/cproc scope 的 CPROC 写入/回读/新帧/恢复，
不代表 AE/AWB 可写或 23/34 个模块完整恢复已通过。

批量应用曾返回 -5，后续逐模块定位到 color_process 路径；cproc 自身的独立 mode 和
manual 字段回读正确。不能由批量错误断言 CPROC 被固件拒绝；
SDK 错误与 native 归一化回读比较返回 -EIO 分阶段记录。
官方库 CP_1_2.state=2 对应 AUTO，不表示模块关闭；
CPROC mode getter 不能机械套用 AE/AWB 模式资格限制。
库中 BT.709 limited 声明仍不能替代运行时输出色彩资格。

本轮 CPROC 中性参考/小幅对比度以及 NR2D AUTO 单叶子实验，已有实际写入、
独立回读、新帧和原始状态恢复证据，但没有可靠文字细节或噪点改善。
EE 小幅实验只取得一张候选后遇到 -43，并有构图变化，不能认可画质。
故障时的恢复与后续显式恢复各自看真实回执，不以一张候选或相同 hash 宣布完整恢复。
顶灯 flare、剪切、偏色与细字偏软仍需按现场目标检查；
这些实验值不作为插件默认调参序列、通用范围或推荐 tuning。

## 2026-10-15 晚间的时序候选与回滚经验

同板后续用 VIN/SIF 独立测得约 46.46fps、FS 间隔 21/22ms，原配置却声明 30fps；
停流保留 handle 的 SDK 读回确认 VMAX2250、HMAX1066 和 24MHz/720Mbps 表。
不能只凭参考时钟字段或比例把模组实装 INCK 写成已测事实。

私有完整时序候选曾取得主机约 29.993fps、SDK 30.000fps 和 33/34ms FS：
采用 upstream 37.125MHz/891Mbps 组、RX aggregate3564、HMAX1100/VMAX2250，
保留窗口/保留位，standby 配置并在 operating 后等待 100ms。
但后续启动仍出现 0 帧、get -43、PHY fatal0x10c、boundary/sequence 和 IPI reset。
它是被实机验证并发现稳定性缺口的实验候选，不能注册为通用推荐 profile、自动修复或默认值。
输入时序成立、连续采集成立和 ISP 画质改善必须分别验收。

时序恢复另设 ledger：保存原 Sensor 字节和 RX profile；确认旧 native 已关闭后，
fresh 原后端，核对原寄存器、RX2880和严格递增的新帧号/时间戳，再确认完整恢复。
ISP module hash 恢复不覆盖 Sensor/RX；sensor 字节恢复也不代表 RX 已恢复。
正常退出及一次真实 get -43 失败的独立恢复均有实测证据，失败仍不得无限自动重开。

contrast1.2 和校正时序下 EE48→52 都没有可靠文字改善，已恢复；
后者有 275 次成功 SDK 取图、约57.93秒时间戳跨度及9张前后/恢复图。
前者的首张候选和首张恢复可见过渡，故 getter hash+新 frame_id 不能单独证明参数对像素生效。
按实际缓冲深度排除在途帧、比较多帧稳定结果；本次 discard12 不是所有 SDK 的通用保证。
不要把这些受控工程实验标记成后台模型自主 Run、标定完成或最佳 tuning。

候选参数来源：[固定版本 upstream IMX415](https://github.com/torvalds/linux/blob/0fcb05b72344f40806cbe810de8872f1698bf053/drivers/media/i2c/imx415.c)。
公开代码支持这些时钟组合，不等于确认亚博模组的实装晶振或保证其 X5 适配。

再以 settle=0 的 SDK 默认路径作单变量接收侧试验，67次取图及原profile完整恢复通过；
后续约80秒预览窗口测得 VIN2486帧/30.003fps，PHY/CRC/边界/顺序错误计数为0。
这仍是私有临时候选，不自动晋升为长期稳定、重开稳定或冷启动合格配置。
官方 FAQ 对0的自动计算描述，应与本版 PHY 实现区分：
[公开源码](https://github.com/D-Robotics/x5-drv-camsys/blob/22c7c2e870622fe779d832ef1753b27191772cdd/mipi/hobot_mipi_phy_ops.c#L569)
的0分支保留/读取默认 settle，非0才写 override，HS范围另按aggregate/lane选择。
未绑定板上kernel源码和实值时，不把它表述成891Mbps专用自动标定或据此给通用手动settle。


## 2026-10-15 文字场景复验：参数回读与像素稳态分别判断

默认settle=0候选的一次600秒上限预览已结束：1991张预览帧、0次ISP写入、closed=true，
随后fresh原Sensor/RX完整恢复并独立取得3帧。600秒是请求上限，回执不提供独立实测总时长；
预览取图数不代替VIN输入计数或连续30fps验收，也不证明冷启动、多次重开或长期稳定。

固定4K文字场景先保存原始3张且0次ISP setter，再分别测试EE AUTO第一槽第一系数48→56、
NR2D AUTO sigma第1分量2.0→1.6；原始/候选/恢复各3张，两轮均无可靠文字可读性改善。
各轮2次setter含恢复，有独立回读和恢复后新帧，ISP journal及Sensor/RX完整恢复分别确认，正常关闭。
这些是可核对的受控实验，不是默认tuning参数、硬件安全范围或模型自主Run资格。

首轮NR的前两张恢复图仍见过渡，不能因discard12、配置hash和新frame_id就判像素已稳定。
另一次同参数复验在每次capture前drain约2.028–2.130秒、实际8–23帧，共9张；
ISP和Sensor/RX恢复已确认，独立视觉审查仍无可靠文字改善；恢复3张颗粒与清晰度一致，
未再见上一组明显平滑过渡。保留EE48和NR sigma第1分量2.0，不晋升best。
保留每次实际等待和drain计数，比较同场景的多张图；2秒仅是本次排队缓解，
未形成通用队列fence或像素收敛门槛，不把恢复后的过渡帧直接用作画质结论。

AUTO第一槽被改写、独立getter回读一致，不证明该槽当前active；analog gain=1也不证明total gain=1
或AUTO插值区间。`sigma_scale[0][0]` 的2.0→1.6只表示首个sigma分量变化，不能表述为总降噪强度降低20%。
4K文字左糊右清是持续观察，对焦、景深和目标平面倾斜仍须受控物理对照，不能据此诊断硬件损坏。
归档收据SHA-256、每阶段配置、SDK帧身份与恢复结果；共享知识不带原图、私有路径或连接凭据。


## 2026-10-15 远距离文字对照：保留 EE48

焦环由用户确认未动，物理调整预览0次ISP写入。拉远、卡面近似平行后，在原EE48下细笔画更可分，
左糊右清差距减轻；但物距、姿态和视场同时变化，只支持待进一步核实的光学几何影响，
不能给出定量锐度收益、唯一原因或损坏诊断。

远景EE AUTO首系数48→64（系数+33.33%），仅在本次operator factorMax=1.34及私有preset envelope内试验；
这不是官方推荐值或硬件范围。候选/恢复计划各只含一个`auto_attr.sharp_gain_0_0`字段。
原始/候选/恢复各3张4K图，9张metadata的exposure=21592.59282052517us、reported gain=1一致；
同一文字ROI无明显组内过渡。独立视觉审查无可靠新增笔画或可读内容，移动背景人员不作ROI，
保留EE48，不晋升best。ISP配置、新帧、journal及Sensor/RX完整恢复分别确认，正常关闭。

安装SDK头的sizeof/offsetof仅用于离线解析已有baseline raw，未获取当前硬件状态：
归档AE again/dgain/ispgain均1；EE autoLevel10、gain轴1/2/4/8/16/32/64/96/128/255，
sharpGain前两行[48,48]。它们仍是配置值，不能证明effective EE、AUTO活动槽或插值结果。
记录原始收据/解析日志哈希及证据边界；仍运行的局部预览不记closed或完成。


## 2026-10-15 EE raw current 往返观测

另一次仅作配置观测的probe，将同一EE AUTO首系数48→64→48，实际候选/恢复计划各仅一个叶子；
9次raw SDK getter按原始/候选/恢复各3次，manual/current sharpGainUp为47→63→47，down恒47，
模式AUTO未变，AE again/dgain/ispgain均1。它增强参数采用证据，但仍没有帧applied序号、活动AUTO槽
或插值权重保证，不能标记逐帧应用认证，也不推导表值与current恒差1的通用公式。
该probe没有归档图像；恢复后两次AE曝光发生变化，不作画质ABA，也不替代此前远景9张PNG的质量评价。
ISP scoped恢复、native关闭及独立Sensor/RX完整恢复均通过；默认仍保留EE48/NR sigma首分量2.0。

[官方SDK §5.7.4](https://developer.d-robotics.cc/x5_sdk_doc_v2.0.0/en/multimedia_development/5-ISP_Tune_API_zh_CN.html#interface-description)
说明tuning JSON state2的AUTO可读取current与auto；
[EE头文件](https://github.com/D-Robotics/x5-hobot-multimedia-dev/blob/main/usr/include/isp_feature/isp_ee.h)
将manual结构说明为current配置。normalizer清零AUTO manual分支是可恢复配置hash的稳定化，不能把0当模块关闭。
分别保留raw current诊断和可恢复config hash；软件快照不能替代像素生效或最佳画质验收。
最终4K预览19:55:47以600秒上限启动，最近报告仍运行；没有退出回执前不记closed。


## 2026-10-15 固定光学条件后的色调与来源核查

固定场景完成15张4K对照：原AUTO→保留实际sat1.1的手动参考（contrast1/bright0/hue0）→contrast1.12→再bright-4→恢复。
前12张exposure约20641.975us、gain1一致；恢复3张曝光漂移，不用于亮度因果ABA。
独立审查两候选均无可靠灰雾或文字收益，不保留；ISP scoped原hash/新帧/journal、native关闭和Sensor/RX完整恢复通过。
这些数值是失败候选记录，不是推荐。光学固定后继续已支持的ISP评价，反复要求调焦不能替代完整ISP工程检查；
截至该轮probe，Gamma/WDR数值接入、AE/AWB模式往返及active tuning来源仍属待办；模式往返的后续实测见下文。

一次native-only来源trace受SIGALRM打断finally，未见closehook且无receipt；确认PID/FD owners消失后显式恢复，
原时序全journal/RX、closed及18帧通过。初始frame_id=0合法，最后3帧正号/时间戳递增才构成最终新帧证明。
仅私有脚本改用单调deadline、owned relay、幂等stop和closing guard，7/7 AST测试通过；没有更新或安装插件代码。
随后getter-only安全探测12秒请求上限内28预览帧、0ISP writes，closed和独立Sensor/RX完整恢复通过。
AE/AWB分别以0/1初始化，getter均SDK0并返回0；当时只证明AUTO场景覆盖初值，没有Manual往返，未据此解除模式资格；后续已另作往返实测。
该native trace只见sensor DSO加载、未见tuning JSON open/read且SDK log为空，active来源仍未确认；
probe自身receipt写入与tuning读取分开，已有service或内置数据尚未排除。Python effectLibrary snapshot自行读文件不能当SDK加载证据。
最终600秒上限预览最近报告仍运行，不提前写closed；默认EE48/NR2.0、最佳画质仍未验收。


## 2026-10-15 后续实测：AE/AWB 当前数值模式往返通过

在同一RDKOS3.5.0/multimedia3.0.5-dev3.0.4、IMX415 4K RAW10 4-lane私有时序profile，
分别保留当前AE/AWB数值，仅作AUTO→MANUAL→AUTO：共437帧、4次setter。
每模块以seed0/1初始化getter均实返MANUAL1，38次manual观测均为1；恢复后seed均返AUTO0，
38次恢复观测均为0，normalized原hash匹配并取得新图；native关闭及独立Sensor/RX完整恢复通过。
这更新了此前“只读AUTO探测尚无往返”的时点，不覆盖旧probe的证据边界。
资格仅限本SDK/profile和本次current-value模式往返，未改手动数值；不扩大WB数值范围，
不宣称numeric response、RAW replay或最佳画质通过。正常adapter的`modeReadbackEvidence`配置仍空，
私有验证结果不自动替代产品适配器的显式证据绑定。完整active effect来源仍未确认。


## 2026-10-15 固定 AE/AWB 的 Gamma 与 WDR 负结果

模式往返资格后，在同SDK/profile冻结当前AE/AWB数值，分别做有界私有试验。
Gamma共789帧/9次setter、21张4K图，测量阶段曝光21.28395065665245ms、WB B增益2.6005859375固定；
current转manual-neutral无可见差别。64点LUT在0..1023内保持单调、X不变，分别下压16/32，
独立实际PNG审查均只压暗，无可靠文字、暗部或噪声收益，不晋升best。
WDR共704帧/8次setter、18张4K图，测量阶段曝光20.691359415650368ms、WB B增益2.6044921875固定；
current manual-neutral无差异，contrast384→448在本轮文档字段边界[-1023,1023]内，仍无可靠收益。
两轮各自曝光/WB/目标模块的normalized原hash全部恢复、取得恢复新帧，并确认native关闭及Sensor/RX完整恢复。
三项候选均被独立图像复核否决为最佳；保留原Gamma/WDR配置，不把16/32/448固化为推荐值。
这些是源码知识中的受控工程记录，不是模型网关自主Run、产品适配器安装或新ZIP发布。
Gamma/WDR已完成的私有数值试验与正常adapter的证据绑定、范围资格分别管理；
WDR strength128的后续否决、像素恢复边界和新boot基线见下文；不推定未验证根因。


## 2026-10-15 WDR strength128：配置恢复与像素恢复分开

后续固定AE/AWB试验`54fb284a2994b8d2`共693帧、8次setter、18张4K图，
WDR strength从0试到128（本轮所用文档字段范围0..128，非推荐值）；
曝光20.555555820465088ms、WB B增益2.6103515625固定。独立图像复核认为候选更亮、更雾，
无可靠文字细节收益，否决为best。同管线恢复AUTO后，exposure/AWB/WDR的normalized原hash均匹配，
但恢复图仍偏亮；journal的`completed_all_originals_restored`只能证明本scope配置恢复，
不能升级为像素恢复。持久观感变化的机制未定，不归因为某个SDK、AE或WDR缺陷。
本轮确认native关闭和独立Sensor/RX恢复；该恢复也不代表完整ISP像素状态复原。

随后fresh只读基线`e24cdce4101ecb62`共206帧、0次ISP写入，导出7模块快照与3张新图；
同纸面ROI报告的码值均值为175/179/203，观感回到原先范围，但该统计不属于校准画质指标，
不证明逐像素一致或故障根因。snapshot SHA-256为
`f597f83820d647b708f4f7d3405971e0bca09cac86bea546cdccdfbc9caa6e84`。
这份公共模块快照不是完整厂商效果库替代品；重放仍需匹配profile/layout和私有原快照。

## 2026-10-15 重新上电：新boot基线和资格边界

此前SSH超时对应用户明确确认的拔线/断电，不作为ISP崩溃证据。重新连接后boot为
`98bc59d6-7599-4c16-ae9f-db5f4358194a`；只读预检核对系统包和全局sensor/tuning哈希未变。
新boot只读基线`730f2b0bb10f096c`共215帧、0次ISP写入、7模块快照和3张新图，
native正常关闭、Sensor/RX独立恢复通过；snapshot SHA-256为
`6fceee7987a31a34d7c17226faadb0b50cf53b34a200350c399c1239b461282d`。
新图几乎灰色、缺少文字，不能把采集成功记为文字清晰度或ISP画质通过。
只读预览`2335ace886b41d67`后来主动结束，共1163帧，closed和Sensor/RX完整恢复已核对；不作为画质通过。

旧boot的AE/AWB current-value AUTO/MANUAL/AUTO资格只适用于当时SDK/profile/运行条件；
新boot重新资格验证前不自动沿用；本boot后续复验结果见下文。正常adapter的`modeReadbackEvidence`仍空，
私有Codex监督试验仍不属于模型网关自主Run。全局tuning文件哈希已核对，active加载来源仍未确认；
不把本轮负结果、只读基线导出或实时出图包装成“最佳ISP配置已完成”。


## 2026-10-15 新boot模式复验、RAW首尝试和20ms失败恢复

新boot再次执行`79a06eaf48943881`：435帧、4次setter，AE/AWB各保留当前数值做
AUTO→MANUAL→AUTO。两模块manual均38次、恢复分别38/37次观测，seed0/1 getter
分别返回MANUAL1和恢复AUTO0，normalized原hash匹配，5张PNG字节哈希核对通过；
native关闭与Sensor/RX独立恢复通过。此前“新boot待资格”仅是当时时点，已由本次限定资格替代。
资格仍绑定同boot/SDK/profile/私有运行路径，不扩大手动数值范围，也未填正常adapter的证据配置。

RAW首尝试`f1f557e5f004df72`先取得101张NV12预热帧，0次ISP写入，首次RAW采集返回-95，
无重试、未验收RAW帧。该回执的native失败stage为空，不能推定为Bayer、驱动或其它根因；
无RAW replay或标定，顺序RAW/NV12也不属于同帧配对。正常关闭和Sensor/RX恢复已确认。

20ms曝光试验`86a164b8f3bde520`共389帧、6次setter，目标float32秒值
`0.019999999552965164`，实际getter为`0.020000001415610313`，相差1个float32 ULP。
严格包装层返回`strict_module_set_failed_exposure`/-5，本轮状态为
`failed_but_originals_restored`，没有完成SHR物理积分时间诊断或候选画质评价。
exposure/AWB/CPROC各normalized原hash和完整scope hash恢复；AE/AWB seed0/1均返AUTO0，
journal记载3张恢复新图，本次知识整理未本地下载这些PNG字节，不冒充字节复核。
最终native关闭，fresh原RX2880、SDK计数约46.435/s及原Sensor寄存器恢复通过。
不要把getter的近似20ms值升级为已证明Sensor物理曝光响应，更不能当作画质已改善。

## 2026-10-15 私有实验运行时持久化的范围

18个文件已保存为用户私有的版本目录`native-imx415-20261015-r1`；安装器报告manifest
SHA-256为`cbd7fec1f6bd70a37408106fa92162b56508b1c360d9f5b83ab97ab11ad09979`。
只读依赖和文件哈希验证通过，`cameraOpened=false`，没有安装服务，也没有切换当前临时运行路径
或搬移路径绑定的资格。该目录是可恢复的私有实验运行时，不是正式插件安装、开机运行服务或合格ISP配置；
新boot/新路径仍需对应模式资格验证。当前灰色场景不足以作文字细节验收，RAW后续诊断结果待各自新回执。

## USB 网络闪连单独诊断

USB 枚举、ADB、USB 网卡和 IP 连通是不同证据。ADB 可用不代表已建立网络；
看到 AX88179B 仅证明出现相应 USB 以太网设备，不能据此认定已识别 RDK 板卡。
ARP 缓存可能是旧记录，也不能证明板卡当前枚举、在线或 SSH 可用。

出现闪连时先保存 USB 描述符/插拔事件，再核对网卡驱动、链路、实际地址/路由和当前对端响应；
不要把网络断连直接归因于相机、ISP 或 MIPI 错误，也不自动改网络、重置板卡或重复启动相机。
共享知识只保留诊断方法和脱敏结果，不携带内部地址、凭据或本机路径。

## 可复核的公开资料

- [RDK X5 硬件介绍](https://developer.d-robotics.cc/rdk_x_doc/Quick_start/hardware_introduction/rdk_x5)：端口与排线要求；按实际板卡修订核对。
- [X5 VIN 示例](https://developer.d-robotics.cc/x5_sdk_doc_v2.0.0/samples/sample_vin.html)：IMX415 官方模式与采集链路；文档 SDK 版本不代替板端版本。
- [Sensor bringup](https://developer.d-robotics.cc/x5_sdk_doc_v2.0.0/multimedia_development/isp_tuning_guide/Camera_sensor_bringup.html)：硬件、配置与初始化排查。
- [ISP tuning](https://developer.d-robotics.cc/x5_sdk_doc_v2.0.0/multimedia_development/isp_tuning_guide/isp_tuning/isp_tuning.html)：匹配 SDK 的工具和调试前提，不代表插件已完成全部实机能力。


### 2026-10-15 Bayer元数据诊断及再次断连

独立getter诊断`16e9bb5b0b56c814`共75张NV12帧、0次ISP写入。
同创建的camera句柄调用`hbn_camera_get_sns_info(CAMERA_SENSOR_PARAM)`实返-1；
`cam_parameter_t`624字节、sensor结构288字节、pattern容量10字节。
输出的10个零字节来自预先清零，`dataValid=false`，不能把它们当作有效Sensor/Bayer返回。
本轮只证明该查询失败，不推定是SDK版本、具体驱动函数或字符串格式的唯一根因，
不通过猜RGGB或套用tuning文件来绕过RAW Bayer门禁。三张新4K图字节哈希核对，
仍缺少可识别文字；本轮native关闭及独立原Sensor/RX恢复通过。

20ms固定1 ULP差异的私有后续观察脚本已通过20项离线测试，尚未实机执行。
它保留严格setter -5，仅在固定方向float32 bits pair、其余normalized字节完全一致、
失败后新双seed为MANUAL时允许继续只读观察SHR；不放宽生产比较、不重发修正值，
不把诊断继续升级为setter成功、20ms物理响应合格或画质收益。

后续只读debugfs查询期间连接中断；电脑仍枚举sunrise5，但实际闪连网卡消失，
Studio也无可用板卡网卡，ping/SSH均不回应，原因未确认。之前相机/ISP/时序恢复已核对；
本机已结束断连查询客户端，远端只读reader终止尚无法确认。恢复连接后先查boot和
精确匹配的本任务reader、清理其读取，再做新帧验证；不得再次无超时读取debugfs tune。
新boot或运行路径变化须重新做模式资格；当前没有可交付的“最佳ISP配置”。


## 2026-10-16 重连资格、显式恢复与 PHY 启动失败

本日脱敏回执见[重连与恢复证据](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)；仅为源码知识中的私有工程试验，未发布插件或验收最佳ISP。
只读基线`4a92da40cc81e796`成功：213帧、0次ISP写入、7模块快照与3张4K图字节核对，closed及Sensor/RX完整恢复通过。
私有profile资格`772026c312d3a025`在13帧、0次ISP写入时取帧-43，closed=false、Sensor/RX恢复未确认；
独立原SDK显式恢复取得3张新图并核对字节，nativeClosed和原Sensor/RX验证通过，仍是0次ISP写入。
恢复后资格`598cf7c6b33cfa7d`共306帧、2次setter后取帧-43；虽然closed及Sensor/RX最终恢复通过，
AE journal仍pending，不能称ISP恢复完成。其baseline/manual两张图只存哈希、缺本地图像字节，不作画质判断。
随后原SDK显式恢复独立确认AE normalized原hash一致，0次ISP写入；约30.029秒取得385帧，
另有3张正号递增终态帧，原Sensor/RX及nativeClosed通过；该轮3张PNG字节尚未本地下载。

原SDK带早期warm/standby资格`077f20f83eb220ed`114帧、0次ISP写入后取帧-43，closed=false且恢复未确认。
移除该分支后，`233bfc8f84edb126`在同一已失败boot上0帧、0次ISP写入，启动-36、native关闭未确认；
这不是干净新boot对照。软件重启前后boot从`ac905bb3-e6e9-4463-a554-2b3cb4443bb1`变为
`ab920dc0-5005-40a0-9d00-e0a00223b8aa`，全局sensor/tuning哈希未变；新原SDK资格`6ec535196d394403`
仍0帧、0次ISP写入，start-36/stop-37，closed=false、Sensor/RX恢复未确认，软件重启未恢复采集。
本次内核明确记录MIPI2 PHY stop-state检查失败、lane state=0x0、start error=-1；不据此判定硬件根因。
ISP/EE试验已停止，等待用户完成一次电源与Type-C完整掉电后再验证；后续结果单独追加，不覆盖失败回执。
根因未定，只保留“early warm/早期stream-state写入影响”和“密集ISP getter与采集交互”两条未证实假设，
不把它们或硬件、SDK缺陷、私有时序当作已确定原因。

内核的`sensor_cali_name=imx415_tuning.json`及context 0文件名关联加强了运行管线关联该校准名称的证据，
仍不能证明完整加载路径或active效果库完整字节/哈希。私有运行时R2共27文件及7依赖，manifest SHA-256为
`cfbd640a598fa21365876351d319d79dcd042d336404cb35f223d64e2edbd3ec`；重启前后文件/依赖验证通过、cameraOpened=false。
没有安装服务、覆盖全局sensor库或生产插件，不是合格ISP配置；新boot仍须真实模式往返资格。
EE helper 8项、试验脚本11项、stock profile 10项仅为软件准备，尚未验收任何新EE候选。
复用时分别查closed、Sensor/RX、ISP pending/原hash及新图字节；任一恢复未确认先处理它，不能以出图或时序恢复代替ISP恢复和画质验收。


## 2026-10-16 完整掉电后原 SDK 采图恢复（后续状态）

用户随后确认电源与Type-C完整断开再恢复闪连，新boot为`fe654112-dbe2-4f84-a26b-090d3e265cca`；
只读预检再次验证R2及全局sensor/tuning哈希。裸原SDK采图`82007553e1633695`成功：0次ISP写入，
3张正号frame_id/时间戳严格递增的4K图字节均核对，SDK-id速率约46.43528/s、43项原寄存器和原Sensor/RX验证通过、nativeClosed=true。
该回执没有总帧数及closed字段，只报告上述3张终态帧和nativeClosed；不补造总帧数。
复用脚本残留`linkedFailedRun=772026c312d3a025`仅关联旧原寄存器参考，本次归类为完整掉电后的原SDK采图，
不作为跨boot恢复或模式资格。此前“等待完整掉电”已结束；完整掉电后采图恢复仍不能确定前次故障根因。

[脱敏JSON](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)已把旧PHY失败保留为历史，当前改为裸原SDK启动、0.5秒稀疏getter模式观察
`81dd34963bc0ed1e`进行中，结果留空。新stock shim去掉early open/attach/read/warm，停流后才对照
绑定本boot成功cold回执的43项期望，再做SAFE fresh原profile验证；13项软件测试通过。
另4项稀疏采样离线测试通过；少量模式样本不等于连续模式资格，尚无新EE候选或ISP画质验收。


## 2026-10-16 本boot采样模式往返通过；EE中性阶段尚在执行

后续`81dd34963bc0ed1e`已完成：444帧、4次ISP setter，AE/AWB各保留当前数值作AUTO→MANUAL→AUTO，
manual与恢复各6次采样、getter最小间隔0.5秒；seed0/1分别回读MANUAL1与恢复AUTO0，normalized原hash均匹配。
5张PNG字节已核对，closed/nativeClosed及Sensor/RX完整恢复通过，无ISP pending。
资格绑定本boot`fe654112-dbe2-4f84-a26b-090d3e265cca`、该私有运行路径、原SDK profile及native SHA-256
`04e8ca307e9f5192a1a60286a1608abf197929367edb6b37d79d2c998c8cbd59`；journal SHA-256为
`e1cd20f8e9a1f7e8b171553874069947b8dd91ee3a240cf5b414b722abc81aea`。
它只证明这些采样时点的往返，不是连续每帧模式认证，不扩大手动数值/增益范围，也不自动写入正常adapter资格。
完整掉电、裸SDK启动和采样节流没有单变量隔离，不能认定其中哪项修复了之前根因。

[脱敏JSON](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)当前EE中性阶段`016a598c854f54c3`仍在执行、结果留空；尚未接受任何新EE候选。
采样EE脚本13项（含sampling）及原C helper 8项仅为软件准备；模式资格不替代EE数值响应、像素等价或画质验收。


## 2026-10-16 EE手动中性资格失败，原scope已恢复

EE中性阶段`016a598c854f54c3`已结束：398帧、7次ISP setter（AE/AWB冻结各1次、EE SDK失败1次、4模块恢复），
日志明确`stage=sdk_set code=-65545`，不是normalized比较失败；错误码的具体含义与根因未知。
AE/AWB/CPROC/EE的normalized原hash及完整scope hash恢复，AE/AWB双seed均返AUTO0，3张恢复新帧严格递增；
closed/nativeClosed、Sensor/RX完整恢复通过，pending为空。原始/冻结参考/恢复共9张PNG字节已核对。
journal SHA-256为`eb2acef61d0cfc05f95f0f53486cd35f6b69daf578b545d9cbbe6e64a8ba54f0`。
EE MANUAL资格仍false，未取得合格manual-neutral参考，也未执行任何新EE候选；配置恢复不等于像素或画质验收。
即使部分manual标量能与公开表范围对照，也不能据此认证整个请求；LUT/degamma的零值及读写domain差异均未证明是原因。

[脱敏JSON](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)下一步仅记准备中的EE AUTO首ISO down槽64试验，尚未执行，64不是推荐值。
已归档的旧AUTO up首槽48→64曾观察current up47→63、down仍47，仅作为分方向排查线索，
不证明本boot down槽已响应。继续保持AUTO，不重试未取得资格的MANUAL；新结果须有独立回执及真实图像对比。


## 2026-10-16 EE AUTO down64有当前值响应，无可靠文字收益

`a798f93f9b7f0082`完成：560帧、8次ISP setter，原始/冻结参考/down64/冻结时恢复/全部恢复各3张，
15张实际PNG字节均核对。EE保持AUTO，首ISO表[up,down]从[48,48]到[48,64]，
current从[47,47]到[47,58]，恢复为[47,47]；首槽活动、插值权重及逐帧应用关系仍未认证。
root与独立图像复核均未见可靠文字笔画或可读内容提升，不接受down64；全图光照漂移不能归因EE。
4scope原hash及完整scope hash恢复、pending为空，closed/nativeClosed及原Sensor/RX验证通过。
journal SHA-256为`09ccc29cff02201dd68b89f1c77b62a0c01767f02dfce2de2297623cae9a3a4a`。
这证明本次AUTO down字段的配置/current响应，不能反推MANUAL已取得资格，也不能当作画质验收。

[脱敏JSON](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)已记录该候选否决及原参数恢复；下一组AUTO [96,96]为独立有界试验
`915eb3fddcd4548c`进行中，结果留空，不预写成功或推荐值。两组候选不能因当前值变大就自动晋升best。


## 2026-10-16 EE AUTO both96同样否决，恢复默认

`915eb3fddcd4548c`完成：555帧、8次ISP setter，15张源PNG字节已核对。
EE AUTO首ISO表[48,48]→[96,96]，current[47,47]→[84,84]→恢复[47,47]；
root与独立图像复核均无可靠文字笔画/轮廓提升，纸面与蓝色标签也未见明确降噪，不保留该候选。
4scope原hash及完整scope hash恢复，closed/nativeClosed及Sensor/RX完整恢复通过、无pending。
journal SHA-256为`692fa91e48060f500bc75c587c2775f246c0d6519c63017e5e05620f4746ec73`。
EE继续保留原AUTO表[48,48]；MANUAL资格仍false，数值响应不升级为画质收益。

[脱敏JSON](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)下一项仅在本地准备固定AE/AWB的CPROC contrast1.15、brightness-4对照，
尚无runId或执行结果；它不同于先前未锁AE/AWB的观测，仍不能预判有效。私有runtime R3仅准备并上传，尚未安装；
R2验证和本boot采样资格不能自动授予R3新的资格或代表插件已发布。


## 2026-10-16 新原SDK基线、固定AE/AWB的CPROC负结果及R3

只读基线`b4e1a52b9635767d`完成：207帧、0次ISP写入、7模块快照与3张PNG字节核对；
closed/nativeClosed及Sensor/RX完整恢复通过。config digest为`18e0f1b86bbfe25343d4f3cd366541568e07a79ab29f65af73fb3d1d8280eb6a`，
snapshot SHA-256为`00f106b2bd33e2f34770e65b529df1d3fb8b81f843e3397b9eb6a1b2264128d0`；
这是公开模块范围的可恢复基线，仍非optimized，也未认证active效果库完整字节身份。

固定AE/AWB的CPROC `d0ea6b88071831ce`完成552帧、8次ISP setter，15张源PNG字节均核对。
实际MANUAL contrast=1.149999976158142、brightness=-4，保留原saturation/hue，EE始终原AUTO。
root与独立复核认为既有文字对比稍强，但没有新增可分辨笔画，纸面颗粒增强，上方白区/全图输出clip扩大，
因此不接受为通用最佳配置；这些仅是NV12转PNG后的码值/观感，不能说Sensor RAW饱和或动态范围已测量。
4scope原hash及完整scope hash恢复、无pending，closed/nativeClosed及Sensor/RX完整恢复通过。
journal SHA-256为`d1649f3daf89732cd695b7efd06e252dc4f13ab942bf9678b5aafa167e9e7ed0`；候选已恢复原值，未交付最佳ISP。

R3现已实际安装为私有实验运行时，40文件/9依赖验证通过、cameraOpened=false；manifest SHA-256为
`ca4c938ec441615091a74f6ee1fee667a34db8a7ad3f782225c4283034eb318c`。它不复制历史图像、boot寄存器参考或模式资格回执，
不启服务或覆盖全局sensor库，不是生产插件发布；新路径仍需fresh原SDK采图与对应模式往返，安装不授予资格。
[脱敏JSON](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)上述记录完成时，下一步为只读审计bare-start时序候选可行性；审计收口见下节，尚未执行新时序候选；
物理INCK仍未知、timingCorrectnessQualified=false，不宣称修好时钟。此前“CPROC仅准备/R3未安装”是历史时点，以上为后续实际终态。


## 2026-10-16 只读Sensor源码审计收口与下一步

[固定3.5.0初始化选择](https://github.com/D-Robotics/x5-libcam-sensor/blob/5cc4c711fe24263da2f87ee02e32c962f3c38034/imx415/imx415_utility.c)与[4lane表](https://github.com/D-Robotics/x5-libcam-sensor/blob/5cc4c711fe24263da2f87ee02e32c962f3c38034/imx415/inc/imx415_setting.h)只读审计完成：声明24MHz，按fps/config_index选择，未见37.125MHz完整normal-start入口。
该utility不消费sensor_clk/extra_mode/sensor_param来切换初始化表；旧19寄存器精确匹配不授予新profile启动资格。
81000和line/1.2不能单独判错或随意修改；源码不等于已安装DSO，实际时序/SHR/曝光单位仍未认证。

上述只读审计时仅做空namespace预检，/usr/include范围缺少6个私有/legacy头是当时状态，libserial有限.so搜索也不证明全盘缺失。
后续已补齐匹配SDK/header构建闭包，原版私有Sensor DSO编译及私有/实装DSO的typed metadata ABI核对通过；metadata预检未调sensor回调/attach/stream/ISP setter，不授予profile运行资格。
用户已答复不清楚PCB/晶振但授权继续有界试验，不再等待规格答复；物理INCK仍未知、timingCorrectnessQualified=false。
原SDK独立观测`cd053f7c90dd60e7`中，20.00172秒取得929个连续唯一缓冲帧；first-last主机/SDK跨度19.98477651/19.984795秒，928个ID步，交付间隔约46.43535/主机秒。
1224行逐帧样本及3张PNG字节核对通过；这确认本次ISP缓冲连续交付cadence，不是物理INCK/37.125MHz测量，也不替代后续候选的独立宿主原DSO恢复。
此前control `28bbed0875c2c5c0`的私有重建原库B与独立宿主Aafter均0帧、start-36/stop-37、PHY stop-state=0x0；nativeClosed=false、fullProfileRestored=false，当时启动恢复未通过。
任务进程组已退出且宿主原库哈希未变，只证明清理/文件边界，不能写成管线恢复成功。该control失败保持原记录，不复用“control已通过”；后续有界startup结果如下。[审计证据](../../../../../.codex/artifacts/x5-imx415-recovery-20261016/hardware-evidence.json)保留来源哈希与边界。


随后`b41c8662d573f4e2`在私有namespace以完整init候选完成首次startup/cadence观察：302个连续唯一measurement缓冲帧、301个ID步，SDK约30.000025/秒、主机约30.023338/秒，RX3564/settle0及43项停流寄存器核对通过。
随后独立宿主原DSO新进程取得466个连续唯一帧、465步，SDK约46.435297/秒、主机约46.469547/秒，RX2880/settle10及43项原寄存器、两子native close和父fullProfileRestored均通过；宿主原库哈希未改。
两份逐帧samples及6张PNG字节独立核对；0次ISP setter/外部手动寄存器写入，但候选init包含19项时序值和1项状态差异，不能说Sensor配置未改。
此前originalControlPassed仍false、sensorInitTableExecutedProven仍false；本次只授予有界startup/cadence观测和独立宿主恢复证据，物理INCK、SHR/曝光单位、完整timing正确性及画质仍未认证。
该次6帧为杯子/顶灯、无文字卡，不能与旧文字场景判清晰度；当时计划的后续稳定性试验结果见下文。


后续首轮稳定性试验`3259e4a367765ed1`中，候选与独立宿主原库均在`hbn_camera_attach_to_vin`返回-207，0帧，未进入计划的60秒measurement；两子nativeClosed=true、进程组已退出，但父fullProfileRestored=false，该轮原管线恢复未确认。
匹配SDK头将207定义为HB_CAM_I2C_WRITE_FAIL，内核记录camera_init_result失败；这与此前PHY start-36是不同阶段，尚不能据此认定线缆、供电或其它唯一根因。
第二轮不执行，R4未安装、备用PHY/stopcheck变体未启用；该时点下一步为只读I2C核查；后续attach-only及full恢复结果如下，不能以b41c历史成功覆盖失败。


原SDK attach/init-only `36bc6270d4e2b1f9`随后返回0，6项powered readback符合原表、nativeClosed=true，但streamStarted=false/fullProfileRestored=false，不属于开流或恢复。
独立fresh宿主full恢复`3a0a69178a135ae9`再次0帧、PHY/vflow start-36/stop-37，nativeClosed=false/fullProfileRestored=false，进程已退出、宿主5e原库未改；该次仍未恢复，错误阶段与之前attach-207分开。
本次真实SDK日志由`/usr/bin/logcat -d -v threadtime '*:V'`的默认buffer取得，`-b main`未含本次内容、旧`/usr/hobot/bin/logcat`路径不存在；筛选4个已知任务PID后388条ALOG，实际runtime gpio_num=1/gpio_pin351与DT信息吻合，不据此操作未证明翻译关系的sysfs429。
独立0623 native的严格编译/config gate及23项离线测试通过后，实机试验`dc29cfce9fa2e8ad`已失败：候选actual need0/start0/nocheck0，kernel确认LP11检查确实移至init，却仍以0x0超时、SDK−10、0帧，未到sensor_start；候选nativeClosed=true。随后独立原库actual 0/1/0在start阶段LP11失败（SDK−36、nativeClosed=false、0帧）。两进程组已退出，原参数0/1/0读回通过、无额外fallback写入，parameterRestored=true而fullProfileRestored=false。marks/kernel窗口SHA与子回执均已核对，不能把参数恢复当开流恢复。

最后两次有界诊断`f99a638f7fded5bc`与`77a74c98962b089d`采用同一私有Sensor152a/native2af2，actual need1/start1/nocheck0，typed配置ppi_pg0（非硬件status）。候选分别在60.005/60.028秒取得1801/1802个连续唯一缓冲帧，主机间隔速率30.000038/30.004201每秒、SDK29.999993–30.000010每秒；各轮0跳号/重复，独立kernel窗口均有实际check HS→entry HS且候选无LP11检查。原receipt的hsReceptionCheckExecutedProven/stopCompatibilityQualified=false保持原文，外侧kernel证据另记，HS仅证明clock lane。

每次候选组退出后均实际写need1→0并读回0/1/0，才启动fresh宿主原库；原库各10秒取得467/466帧（SDK约46.43526每秒、主机约46.55596/46.50661每秒，保留差异）。两轮各6张PNG/逐帧样本字节、43项原/候选停流寄存器、RX、native close、组退出、最终原参数及父fullProfileRestored均已核对。这是两次独立60秒观测及两次原库恢复，不能称连续120秒、长期/冷启动稳定、唯一根因修复或ISP画质成功。最新f99a画面下半部已有较大的Yahboom文字卡、上方仍有顶灯；本轮A/B未锁AE/AWB，不能判定ISP清晰度收益，也不再要求用户移动/调焦。物理INCK、SHR/曝光单位、RAW/标定与完整效果库身份仍未认证；不再继续盲试。R4-stopcompat私人备份已安装且只读validator通过：17复制+3生成文件、7项SDK依赖，manifest `248cb7fdf8440304b3471e63b592ffed4cc231bccf754e16ea3bafc896637ffe`；未加载DSO/激活相机、未建service/替换全局库，不继承旧模式/RAW/时钟/画质资格。安装后只读checkpoint确认原driver/tuning/libcam哈希不变、原参数0/1/0与有界等待保留、3个所查相机控制节点无owner PID。匹配此profile的新AE/AWB模式资格仅研究方案，尚无新setter。

## 2026-10-16 新boot c983的仅文件恢复与原SDK新基线

重启后boot已变为`c9831385-9d42-4783-a278-e32fa58de6a4`，旧临时目录消失；R4备份manifest仍为248cb7…7ffe。严格file-only rehydrate已核对176份payload、原/候选source-manifest的74/82项与9项SDK文件，未加载DSO/开相机/执行ABI/改参数/迁移旧资格；native Makefile仍依赖外部VP源码，不构成自足可重编译闭包。随后root另行在本boot重跑两份无callback纯ABI；确定性metadata hash相同不等于沿用旧运行资格。

新原SDK裸采图`d0a369ed91fb4d53`在本boot成功：760条逐帧样本中465条measurement、464连续ID步，主机/SDK间隔速率46.435446/46.435282每秒，3张新4K PNG字节核对；43项实际新寄存器、原RX、native close及parent reaped/group absent通过。原参数由boot初始0/0/0变为原SDK的0/1/0。本地新43项reference SHA为`e9b6b8d67d356038aa51846b36e5078cb3fb92e96340baece1c09a05d1307932`，该新基线记录完成时尚未上传，随后上传验证见下段；不使用旧boot参考。旧fe654的两次60秒candidate仅为历史，本boot新profile尚无startup/mode资格；43项离线mode测试通过但实机0setter。当前文字卡只剩下缘入镜，不请求用户移动/调焦，未取得ISP画质收益。

本boot模式试验`f6e8d70173a932b0`已在pre-ISP连续门禁失败，实机仍0setter、未建立CORE4原快照，模式资格未授予。候选304次get均return0/unique，但头部91…95→107缺11个ID；warm最后release至测量首次get-start有0.530258084秒无get空窗，跳点SDK跨0.4秒而主机仅0.029443375秒。root源码时序审计与该轨迹支持“warm后重型cv2/numpy准备造成旧队列积压”的受控解释，这是推断，不能认定Sensor漏帧。完整头样本保留，不放宽门禁；仅准备将重型import前移至start前、durable intent放到warm前的一次明确修复复测，尚无结果。

新43项参考已真实上传，并由本次manifest `ba4dd651759520eab9c9e159cedc3147fb43850c3cd12216a3410048a5d1e4ca`校验。独立host恢复取得470条measurement和3张新图，Sensor/RX、参数0/1/0、native close及两组退出通过；父fullProfileRestored=false、CORE4 pending保留，原因是pre-ISP门禁前无原快照，并非把0setter伪报为改过ISP。

## 2026-10-16 c983模式复测通过的严格边界

明确修复采样器准备顺序后，复测`3f26eac7d0a14b63`通过原严格门禁：301条measurement/300个连续ID步，主机/SDK间隔速率30.000251/30.000015每秒、比值1.00000787，保留完整头部样本。AE/AWB各做一次保留当前数值的AUTO→MANUAL→AUTO，共4次实际ISP setter（wrapper code0）；5个phase各6个≥0.5秒间隔样本、保持≥3秒。它是中性模式往返，不是0setter，也不是曝光/增益/白平衡数值调优。15张候选PNG、16份raw、journal与CORE4最终归一化原值恢复已核对，pending为空。

候选43项寄存器/RX/native close通过后，进程组退出、实际写need1→0并读回，另启宿主原库取得465条measurement/3张新图、43项原寄存器及close；父fullProfileRestored=true、两组退出。资格仅绑定当前boot c983、该私有runtime路径、native2af2/Sensor152a/RX3564/need1-start1-nocheck0及layout/scope；不同R4备份路径、重启和新binary不继承。MANUAL数值响应、EE MANUAL、RAW、物理INCK、完整效果库身份和最佳画质仍未通过。

f6e8失败/fullProfileRestored=false保留为反例；source-order修复与本次无缺口结果支持软件采样/积压解释，不证明物理时钟或Sensor漏帧原因。本次仍是稀疏模式观察而非每帧模式认证。

最后只读checkpoint（SHA `b8675b6b55c66f5664f64638bf59c99b430613595210a51edf51b2132a7ab1df`）确认原global三哈希/参数未变、无owner/两组退出、完整恢复关闭，无pending且未激活全局候选profile。当前交付为`current-30fps-core4-baseline-20261016.zip`（16项/13,714,449字节，SHA `4ae2eb976579035bfc09780e93a07779af0671e6d933071f4beb6decf3cbb10c`）：当前实验profile默认CORE4恢复基线，非最佳画质。旧7module包仅为历史。source2226修复版45项离线测试通过；独立C11/Werror typed normalizer复算16raw通过（审阅JSON SHA `92d42b6b60354f9744d3bea65ff242a49276cd47056ed234bc4534e21a4b1f3f`）。分别中性模式不证明同时AE+AWB冻结。原journal模块status残留manual_write_pending属于元数据瑕疵，保留原字节；restoreStatus verified/roundtrip、最终原值hash/parent pending[]/checkpoint决定最终状态。


## 2026-10-16 c983联合固定曝光与白平衡实机通过

随后独立协议`4dabf9c6a1804eea`完成AUTO/AUTO→AE MANUAL/AWB AUTO→两者MANUAL→先恢复AWB→再恢复AE，
共4次保留当前数值的mode setter（wrapper均0），未改变曝光、增益或白平衡数值。
5阶段各保持至少3秒、6次保留性采样及3张新4K PNG；两者同时MANUAL的3张图构成本次联合固定基线，
并非画质改善。各模块30次实际getter的最短间隔分别为0.502199375/0.502430834秒，包含跨阶段检查。

新开流前严格连续窗口取得301条measurement、300个连续ID步，主机/SDK间隔率29.999282/30.000006每秒；
SDK/主机时间比0.999975867，无重复或跳号。准备仍在start前完成，未删头部样本或放宽连续门禁。
15张候选图、16份raw及独立宿主恢复的3张图均归档；CORE4原值、43项寄存器/RX和native close通过。
两模块恢复共用固定60秒期限，本次用24.001秒；故障测试确认AWB恢复失败仍尝试AE，恢复不重复。
父进程按candidate组退出→need1清为0并读回→fresh宿主原库恢复执行；宿主465条measurement、43项原值及close通过。
最终checkpoint为无owner/两组消失、参数0/1/0与有界等待、全局库未变、无pending、完整恢复关闭。

父receipt SHA为`b239cca4dac661f581d24a7b87c8fbaf295f86b8e04deb58ab460c9d2130b204`，
journal为`d7781af9a26fac83018f8b36d076410796d6c948518f4c63531c33084b15d463`，
checkpoint为`bbfcbbc8409026c700655c4c47e83c403f57ac013430c564dfc5a4fa66ee4d07`。
联合资格仅绑定当前boot/同一私有runtime/native2af2/Sensor152a/RX3564、CORE4/layout及本次journal，
不能继承到备份路径、其他boot或产品adapter；MANUAL数值响应、EE MANUAL、RAW、物理INCK、active效果库身份和画质仍未认证。
新协议58项本机测试及独立审查通过；这是Codex监督工程证据，未发布为插件可执行原子或后台Agent Run。


## 2026-10-16 曝光数值预检与真实SDK量化读回

`efc2d3c5588340af`和`04732f9651cb4148`均为脚本自己的浮点模型预检拒绝：每轮实际只有4次模式setter、0次曝光数值setter，最终原配置恢复。
双浮点模型同时一致、附近9个离线格点可选等条件没有SDK实证，不能据它们断言SDK无法表示或拒绝曝光值；
它们只适合作为分析假设，不应代替真实typed字段、MANUAL状态、实际范围、受控写入及严格回读。

随后`0554f0638a534d3b`保留实际范围门禁，真实请求一次曝光值：SDK字段由0.020728396251797676请求到0.01658271625638008秒；
strict wrapper返回−5，实际日志阶段为`normalized_readback_compare`。
单次诊断getter返回0，实际SDK字段为0.01658024825155735秒，mode1、其余三个增益仍1。
该raw SHA为`b2ae1e875a68caa7c699240905a2d24666e6b29b820d7f6c20949e0e96359ebb`。
这是实际读回的量化现象，不是物理曝光时长标定，也不允许放宽原严格比较或将失败值认定为成功候选。

原MANUAL raw严格回滚成功（0.239秒），后续AUTO/CORE4和独立原驱动恢复均通过。
本轮真实6次setter为4次模式＋1次被严格比较拒绝的数值候选＋1次数值回滚；没有候选B图或画质收益。
父receipt SHA为`b9bb2f46c31a84d7ad9612e974eaf6c5bd03e0aca269df19beea968e8302fc5b`。
若下一轮用实际SDK返回值构造新候选，应另绑来源raw/版本/布局/模式，重新严格写入、采图和恢复；
这不等于继承失败候选的资格，不把该单个曝光值推广为其他场景或新Sensor的默认值。


## 2026-10-16 实际曝光读回值重新写入与 A/B/A 对照

`1e4722a9f32346fb`使用上轮失败诊断 getter 真正返回的 SDK 字段值，作为**新的一次候选**。开相机前绑定0554来源 parent/journal/raw哈希及相同boot、Sensor、native、layout；只复制该曝光标量到新 live 配置的4字节字段，其余字段保持。不是将失败回执改成成功，也不推导通用曝光步长。

本次 live SDK 曝光字段为`0.021037038415670395`，候选及严格回读为`0.01658024825155735`，实际比例`0.7881455518570902`；不是精确×0.8，更不代表已量到物理曝光秒数。候选写入和原手动 raw 回滚的 strict wrapper 都返回0，回滚耗时约0.334秒。实际共6次ISP写入：4次模式写入、1次曝光数值候选、1次原数值回滚。A1原手动、B候选、A2原手动各3张新4K图；B/A2各6组≥0.5秒间隔/≥3秒的CORE4采样，21张候选阶段图及独立原管线3张图字节均核对。

parent SHA`248bd5424d7bf4699c4a9811026c90b55ed79233165b4d80c2d0623499ac284d`、数值journal SHA`6b10ac15f72c8e50ea3c1d1375b0c18cb21f7329badd3fb77475ae557e10c04f`。原AE/AWB AUTO、CORE4、Sensor/RX、43项寄存器、native关闭、两进程组消失及need1→0后独立原管线恢复通过。最终只读checkpoint SHA`59048422684a278c53bb6a1d4c1bff47cdf8c3afff9c991c7034e194146f8612`核对原全局库哈希未变、参数0/1/0/notimeout0/wait3000、所查控制节点无owner。

图像审核：候选明显变暗，未见标题/标语多出可辨笔画；不接受为最佳画质配置。标语ROI的三帧显示灰度均值约172.311→153.473→171.730，仅是处理后8bit输出码值描述，不能当线性光量、RAW噪声/SNR、MTF或物理曝光标定。本次只通过该tuple下的一次SDK数值写入保持、A/B/A采图及恢复闭环；不授予物理INCK、SHR时序、RAW、EE MANUAL、长期稳定性或画质资格。脚本测试28项通过；知识进入插件源码不等于已发布可执行自动调参工具。


## 2026-10-16 RAW 传输诊断打通与顺序图像边界

默认原驱动路径的 `e5d880cb57494df6` 在 NV12 连续测量阶段先失败（−43），尚未调用 RAW：候选和独立原管线均没有取得完整恢复。0 setter、close、参数回读和进程退出不能代替功能恢复，原失败回执保持不变。
随后 `d4996410a4da4281` 在私有兼容 profile 下完成60秒/1801条measurement（主机间隔率约30.000208），再独立原管线取得465条measurement及3张新图，完整恢复。它支持该受控启动序列能恢复采集，不证明唯一故障根因、物理INCK或长期稳定。

`47aa5a1fbe754f0c` 使用从兼容 native 派生的只读 RAW 诊断库，重新实测10秒连续窗口：301帧、整窗出队率30.000142、首末帧主机间隔率30.000238。新二进制不继承旧模式/数值资格，本次0次ISP setter、0次手工Sensor寄存器写入。取得3份实际3840×2160 RAW10：各16,588,800字节、stride7680、16bit LE右对齐；实际format/layout/cache/唯一对齐及每次release均验证成功。

SDK `hbn_camera_get_sns_info` 三次仍返回−1。诊断输出保留Bayer未知，只允许四个无颜色标签的奇偶采样平面观察；没有猜排列、RAW回灌或标定。源驱动的 `BAYER_PATTERN_RGGB` 是CFA族，`BAYER_START_GB`/`BAYER_RGGB_START_GBRG` 是起点，两者合读为**驱动声明GBRG起始**，不能只看RGGB字符串认定左上是R，更不能把声明当实测物理Bayer认证。

三份RAW各比调用前最后NV12元数据新1帧，并与随后首条NV12的ID/SDK时间一致；保存PNG则晚67/65/66帧，约2.233332/2.166666/2.200000秒。故只能称顺序RAW与ISP观察，不能称同帧配对或用其作精密RAW↔ISP定量标定。实际局部可辨RAW文字，ISP有描边；奇偶平面各半水平/垂直采样、统一显示拉伸且编码不同，不据此宣布镜头根因或画质已改善。

独立原管线再次取得465条measurement、3张新4K PNG、43项原寄存器及close通过；候选/原管线共1361条metadata、3 RAW及6 PNG的实际字节、时钟/ID、私有bind来源、RX、恢复参数与组退出由两次本机独立审查核对。父receipt SHA `1a6d86e3f6bc03412b5e906baae42f4660e4bc5d6badbd18140c64f4b00e43c0`，只读终态checkpoint SHA `586fedd461f4406ad7336ad87d3466e99636203f2a4966bdedcd1d13225ccd14`：无owner、原全局三哈希未变、参数0/1/0/notimeout0/wait3000，完整恢复关闭。SIF size warning/vsize0也在本次成功启动中出现，单条同类日志不具故障特异性。

连续门禁还须防止“10秒窗口里只有两帧”：同时核对成功帧数/整个窗口时长、实际首尾覆盖与边界空窗，不能仅凭两帧间隔约30fps通过。新诊断9项本机测试含稀疏窗口及长首/尾空窗拒绝，未修改旧冻结脚本或旧回执。此项打通的是私有工程RAW传输诊断；不等于产品 `capture_raw/process_raw` 已支持未知Bayer，也不授予最佳ISP配置。


## 2026-10-16 最新边界：EE 减量尚未写入，当前 HS 启动失败

根据RAW局部与已有增锐负例，新准备一次私有EE AUTO首ISO系数对 `[48,48]→[32,32]`，目标是观察亮/暗侧描边是否降低。官方Tuning guide表3.17-2给出sharpGain[2]范围[0,1024]；此处32仅为本次私有响应候选，不是最佳preset，不开放产品中仍只读的字段，也不重试失败的EE MANUAL。真实SDK头编译的纯helper只计算两uint16的候选字节，未执行SDK回调；冻结的2af/152a采集库保持原样，协议包含fresh强10秒检查、当前AE/AWB联合固定、A/B/A、strict回读、EE原raw回滚及独立原管线。7项本机测试和独立预审通过。

实际 `9b3cbf2f82a948cc` 却在进入ISP之前失败：兼容候选与独立原配置均在Sensor start回调返回后，MIPI2高速接收检查等待约3.002秒，PHY_RX=0x0，VIN启动失败/SDK−36；均0帧、0图片、0 ISP setter，未取得候选32/32图像或响应结果。SDK停流−37使两个child `nativeClosed=false`；进程退出后内核设备释放/deinit/reset记录和所有权消失仍不能证明功能恢复。不要归因EE，也不要将早先47aa成功误作最新状态。

父receipt SHA `c6aff38665785cc00f442612b3bdddb3f96423dffe938229d018196a80a5a269` 的 `fullProfileRestored=false` 保留。最后只读checkpoint SHA `29726e35b298d91a860fa71302c2f614e98041249c22ea4040c7ce75414f9c02` 实查原全局三哈希、参数0/1/0/notimeout0/wait3000、无控制节点owner及两owned进程组消失；`streamRecovered=false`、32候选未应用、画质未验收。原47aa三份RAW成功仍属有效历史证据。

头文件的hbn_camera_reset描述stop→deinit→init→start；现有证据未证明它比本轮已执行的新进程生命周期增加独立供电/时钟恢复，当前也无有效旧handle。因此不因接口名称直接重试、跳过HS检查或扩展寄存器/时钟写入。Sensor start done仅是控制调用成功，必须以真实HS/有效新帧确认输出。继续调ISP前需要新的链路恢复证据，并分清模组输出与接收侧；0x0本身不能确定排线、供电或INCK中的唯一原因。


## 2026-10-16 新 boot c988：初始化 I²C 失败与显式清理取证

连接恢复后实查 boot 为 `c988b143-56b6-4558-a5e9-7351b1c2be42`，旧 `/tmp` 私有运行目录已消失。旧 c983 的成功、模式/数值资格及 43 项实机参考不能继承到新 boot；从本机存证恢复脚本、源码并重新编译，只恢复工程输入。历史 43 项值仅作为比较 criterion，本轮没有生成新的成功 reference。

新 boot 两次原配置尝试 `c27becf824f44e2d`、`a80fdd01ae034a5d` 均在 Sensor 初始化数组的第一条 `I²C 4@0x1a: 0x3000=0x01` 写入失败。实际 SDK −207 对应 `HB_CAM_I2C_WRITE_FAIL`，尚未进入 MIPI CSI 接收初始化，均 0 帧、0 图片、0 ISP setter。它与旧 boot 的“Sensor start 后 HS 等待失败/−36”是不同故障阶段，不能继续把最新阻塞笼统归为 MIPI 高速开流。设置 `CAM_LOGLEVEL=4`、`LOGLEVEL=4` 后，stdout 仍未给出 SDK 细节；实测通过 `logcat -d -t 800` 找到第二次实际 PID 6176 的初始化与 11 次 retry 记录。定位时须绑定本次 PID/时间和第一条失败操作，不把“增加日志级别”当作已经取得详细日志。

新的私有显式清理诊断实测记录 VIN/ISP close、camera destroy、flow destroy 和 memory close 调用，camera/memory 实际返回 0，资源 flags 由 127 清为 0，调用者 context 变为 NULL；另有内核 deinit 和无 owner 证据。这是当前失败路径的清理证据，不能代替新帧或完整功能恢复。VIN/ISP close 与 flow destroy 是 void API，不能伪造其成功返回码；flow destroy 日志另有两条 null node，保留原日志，不仅凭它认定节点 ownership 或重复释放。尚未进入接收初始化时，实际参数仍为 `need_stop_check=0/stop_check_instart=0/nocheck=0`，不为匹配旧 postcondition 预先改值。fresh runner v2 先保存 cycle 的主错误/SDK code、真实释放与帧事实，再把参数或 owner 等后置检查错误单列 `finalizationErrors`；后置参数不匹配不得覆盖原始 −207，也不得产生成功 reference 或 fullProfileRestored。

随后从板上实际官方源码编译独立 `vp_sensor_fixed_mipi_host` probe。按 board ID 302 跳过 CSI 1/3，按设备树在 CSI 0/I²C 6/reset GPIO 353 和 CSI 2/I²C 4/reset GPIO 351 做官方复位及芯片读取；两个接口的 `0x1a` 均未成功读取 chip ID，probe 返回 −1（进程退出码 255）。它会尝试 wakeup/standby 寄存器写入，不能标作全只读扫描；失败读取后日志中的 `0x0000` 也不能当成识别到的真实芯片 ID。该次未创建相机 context、未执行 ISP 写入；官方 reset/probe 的失败仍不确定排线、模组供电、器件状态或时钟中的唯一原因。

当前已询问现场模组供电与排线锁扣，等待实物确认；恢复链路后须重新取得本 boot 的真实新帧和参考，再继续 ISP 对照。本记录不宣称 ISP 调好、MIPI 无法修复、硬件损坏或物理 INCK 已确定，保留所有旧成功和新失败的各自证据边界。


## 2026-10-16 清理 ownership 更正：停止 v1，added 节点由 flow 释放

随后对本次实际安装的 `libvpf` 做二进制核验，得到比示例调用顺序更直接的 ownership 证据：`vnode_open` 初始引用为 0，`vflow_add_vnode` 增加引用，`vflow_destroy` 遍历节点时在旧引用为 1 的路径自行调用 `vnode_close`。因此，先显式关闭已 added 的 VIN/ISP 再销毁 flow 存在对已释放节点再次访问的风险；旧“销毁 flow 未必关闭 added 节点，所以先逐一 close”的推断撤回。上节 v1 的 flags 清零、context NULL、内核 deinit 和无 owner 仍是当时实际观察，不能作为该释放顺序安全的证明；v1 停止使用，不将它推广到插件。官方示例之间的不同顺序不能替代对本机 SDK 实现的核验，也不能笼统认为示例顺序均安全。

新的私有 v2 清理方案为：记录 stop 原始错误且继续清理，先销毁 flow，由 flow 释放已 added 的节点；仅对未 added 且仍由调用者持有的节点显式 close，再销毁 camera、关闭 memory。96 字节诊断 ABI 升为 v2，分别记录直接 node-close 调用与交给 flow 的 VIN/ISP 释放路径，不能把后者伪装成直接 close 调用或 void API 返回码。新版 helper、mock/消毒器测试及新实机运行须分别取证；旧 v1 的硬件回执不授予 v2 开流或 ISP 资格。用户随后已回报物理重插，下一次运行仍须读取实际 boot、核对原配置并取得新帧，不能沿用 c988 失败或旧成功作为当前状态。


## 2026-10-16 ABI v2 的本次实机边界：初始化失败退出已观察

随后实机 `4ec6c1537f7e44ab` 使用 fresh runner v3（SHA `a7403b007cfac50793f9e0a9bac996c2946ce0d98d88fdf555b6a2ef33a1d06d`）、原配置私有 native（SHA `fe54afe11829ae57d6ebbf073deeda9b9663b0d44b752c16b124b8e6eb2d4adf`）及 96 字节 ABI v2。boot 仍为 c988，用户回报检查重插不代表已经重启。Sensor attach/init 仍返回 −207，0 帧、0 ISP setter；主错误保留 `camera_stream_start_failed/−207`，实际参数 0/0/0 的后置不匹配另记 `finalizationErrors`，未覆盖主错误。未生成新成功 reference，`streamObservedAndReleased=false`、`fullProfileRestored=false`。

本次清理实际返回 0、context NULL、flags 127→0；VIN/ISP 直接 close 计数均 0，`flow_owned_vin_released/flow_owned_isp_released` 均 1，flow destroy、camera destroy、memory close 均被调用，camera/memory 实际 code 均 0。日志有内核关闭记录，owned 进程组消失、无 owner，未出现 v1 的 `vnode is null`。flow-owned 两标记只记录 void destroy 返回后本地 ownership 清除，不伪造 SDK 成功返回码。本次因初始化先失败，`flow_stop_called=0`；因此它只验到该初始化失败退出路径，**没有验到 stop −37 后继续清理的实机恢复，也没有验到新流、连续采图或 ISP 改善**。只读终态 checkpoint SHA `291da3612e26e9ea6165f2a9aef7fc67b6bf25b2c505b595468dcbe67a80dc43`。私有 helper 的实机观察和正式 native 改动回归、插件发布及运行时能力须分别判断。


## 2026-10-16 后续恢复：本 boot 已重新出图和完成模式回环

本节更新当前状态，不删除上节初始化 −207 的失败事实。`1a099e07387d485a` 以 ABI v2、原 Sensor/原 native 新采465个连续唯一帧（实际10.01379秒，约46.43596次dequeue/秒），43项停流寄存器、新PNG和owned close通过。随后`9752644c1dcb43ad`的私有30fps配置取得301个连续唯一帧（10.03339秒，约29.99982次/秒），退出后独立宿主原配置再次出图并关闭；全局Sensor和效果库未被替换。这些是当前boot的新采流证据，不是物理INCK认证或长期稳定承诺。

I²C恢复过程中，实际已知0x3000指针读取在临时power/control=on时成功；随后auto→on→auto三阶段均成功，最后恢复auto。第一组缺少紧邻的on前失败读取，因此不能认定runtime PM就是−207根因，也不能把永久禁止休眠写成修复方案。控制器空闲suspended不等于通信故障；GPIO352属于GPU供电使能，不能当相机电源操作。

当前boot模式回环`aa4c6df809324f3a`已完成：新30fps门禁后，AE和AWB分别执行当前数值AUTO→MANUAL→AUTO，共4次严格setter，各阶段至少3秒/6次间隔采样，共15张模式PNG；CORE4原始快照、raw回读、图像字节及自动模式恢复经离线复核通过，随后独立原配置新采图和owned退出通过。绑定实际native e1202f…、Sensor152a27…、layout4443c3…及本次journal，不继承旧boot模式资格。前一试验08455d…在快照配置缺sdkVersion时停止，实际0 setter，独立原配置恢复通过；该失败保留。新包装器必须在开流前核对snapshot必需的sensorConfig、sdkVersion、csiPort、cameraMode和stateDir。

以上尚不意味着ISP画质改善。EE数值试验仍须新的固定AE/AWB同场景A1/B/A2、实际写入回读、恢复和图像评价；模式可切换不授予任意数值范围、EE MANUAL、Bayer RAW或生产插件发布资格。私有研究脚本没有自动变成已部署的MCP原子能力。


## 2026-10-16 当前boot的EE减量实机对照

`33a3a1759be74d35` 基于新模式回环实际证据执行joint AE/AWB当前值冻结及EE AUTO首ISO pair48/48→32/32→48/48，共6次setter（4模式+2EE）。current上下沿47/47→31/31→47/47，六次间隔采样和严格CORE4回读均通过；24张流程PNG及独立原配置3张PNG字节核对，原配置重新出图、43项寄存器、owned退出及终态无owner/原文件和参数恢复通过。不能把这次普通关闭路径成功提升为stop−37故障恢复实测。

实际A1/B/A2文字局部未看到可靠新增可辨笔画，雾感和蓝紫色偏仍在，候选已恢复，不作为最佳配置。局部码值和梯度变化仅是processed PNG观测；不当作RAW噪声、MTF或色彩标定。已明确区分“参数写入响应已验证”和“画质未接受”，不因回读31就认定优化成功。完整效果库活动字节身份、物理INCK、曝光时序及当前RAW完整解释仍未认证；研究协议未自动发布为产品原子。


## 2026-10-16 后续取景变化：白平衡数值候选未执行

在确认原图纸面B/G约1.12–1.14后，准备了仅手动B gain减0.25的私有响应试验，单步相对变化最多20%，不把它称为SDK范围或AWB标定。9项本机字节/边界/错误及回滚测试通过。实际`9d3d5022028547f4`的新图已是偏红天花板与直射灯管，文字卡消失；当前图像条件检查阻止了数值setter。因此该轮实际是4次中性AE/AWB模式setter、0次蓝增益setter，不记为白平衡候选画质失败或数值响应通过。

本轮CORE4原值回读、自动模式和新恢复帧通过，随后独立原profile新采图、关闭及终态无owner/原参数0/1/0通过；保持原配置。已请求恢复文字卡或指定新固定目标，没有再请求调焦/断电。新准备的文字卡图像匹配已离线验证：3张历史真实卡面图813–869个几何inlier，当前天花板图被拒绝。旧图只作视觉锚点，不能当新基线；匹配helper尚未接入板端运行或生产原子。下一次应在任何中性模式setter之前先检查当前目标，再按新图判断偏色方向，不能沿用“上一轮偏蓝”对当前偏红场景执行减蓝。

## 2026-10-16 连续采流与白平衡正向结果（当前现场限定）

用户恢复文字卡后，私有工程试验完成三轮有原值恢复的WB对照：`63988d49a18743af`仅减蓝改善偏蓝但略绿；`c7abc9e61a224907`增加少量红色后更中性；`cc292df1537a4a6a`进一步微调，最终R/Gr/Gb/B为1.9091796875/1.0498046875/1.0498046875/2.3720703125。仅适用这颗模组和当时办公室光照，不能作为新IMX415的通用初始值或AWB标定。此前EE/Gamma/WDR/NR2D无可靠画质收益，未纳入。

保存预设后，`d2e77d49b4334ab6`、`6b0d64bea9784377`各自从新进程加载固定gain，保持AE AUTO，严格回读及15秒/6次采样、实际新4K图、SDK配置/快照导出均通过；每轮结束恢复原AWB AUTO并独立重新打开原驱动采图、关闭，最后无owner且参数0/1/0。最终纸面4个ROI B/G从1.16–1.18变为1.018–1.025，恢复后又回到1.16–1.19；视觉蓝雾减少，文字无可靠新增笔画，直射灯光晕仍在。不得改写协议中的qualityAccepted=false来冒充模型验收；主观现场选择单独记录。

采流方法：SDK取帧/释放必须只有一个持续消费者；主线程请求复制的新帧后可编码、落盘和分析，后台继续取帧。6/24张图的保存及几何匹配不能阻塞采流。FramePump真实试验639取得2908帧/24图、退出join成功、无SDK错误，取帧间隙最大约50ms；之前同线程保存有秒级间隙并出现−43。这支持该场景的改进，不证明所有−43的唯一根因。SDK控制读写和取帧通过已验证的ctx互斥串行化，停止时先join消费者再关闭native，保留首个SDK故障。

目标守卫应使用当前图和几何匹配，不能因卡片平移/透视变化就把真实目标当成消失；较重匹配只能在持续采流下执行。fine轮随后的原驱动init曾−207，必须保留失败；独立恢复`4aad6d861dfa4106`随后通过，不合并成“从未出错”。保存的配置应带实际gain、SDK/库/布局/boot绑定、原值与A/B/A证据；新boot重新资格核验。预设存档不等于全局自动启用，私有脚本验证不等于已经部署的插件原子能力。

## 2026-10-16 曝光、降噪、锐化系统选优（覆盖此前仅WB结论）

完整方法见[系统性ISP调试流程](systematic-isp-search.md)。本轮11个完整实机试验通过，246张新图字节哈希核对；另保留2个失败尝试及独立恢复。比较了AE target36/42/48/54/60、NR2D有效ISO表3分量0.5/1/1.125/1.25/1.5、3DNR96/128、EE32/48/80、对比度1/1.05/1.10。3DNR向上请求被128上限截回原字节，是no-op，不能记为增强有效。

当前办公室纸卡场景最终选择：原WB四通道、AE AUTO/FIX target54、NR2D全部有效档sigma×1.25（当前[2.5,2.5,5]）、CPROC MANUAL contrast1.05且原亮度/饱和度/hue不变；EE和3DNR保留原值。77d57a8a7bdd4fd5与独立重放5b8fadf22ba54b41均实际加载、15秒/6回读/新图/SDK导出/恢复及独立原驱动重新出图通过。最终仅CORE4 SDK快照与补充NR属性分别导出，3DNR数字观察来自其单项试验，不拼成“全模块逐值读回认证”。

相比仅WB，主卡曝光与对比更合适；未恢复缺失笔画、灯光光晕仍在。提高曝光/对比会增加原灯区高光截断和某些区域processed码值波动，不能宣称整体噪声或清晰度都提升。最后恢复原默认并关闭，选定预设独立存档，没有自动开机启用。该数值仅作历史证据，不是下一颗相机的默认推荐，也不代表产品后台Agent或插件已发布。

新验证的故障方法：mode offset按各模块descriptor取值（AE为8、EE/NR为0，仅限当前头文件）；写前gate失败保留0次setter记录，新进程重试，禁止降低gate；恢复时尝试全部已改模块，逐模块严格回读，最后再做全scope比较，避免把清理中的混合临时状态误报成恢复失败或跳过后续模块。纯FramePump源码已纳入skill脚本并通过4项并发/故障测试，组合清理7项测试通过；宿主尚未自动接入，不能因此称新增MCP原子可用。


### 2026-10-19 补核厂商调焦机械边界

[亚博官方新增调焦注意事项目录](https://github.com/YahboomTechnology/IMX415_Camera_Module/tree/main/0.%20Precautions%20for%20Focus%20Adjustment%20%28Must%20Read%29)含一页PDF，核查SHA-256 `2cb9ecdc94edf3cfbc1dd6a81b903f1892f8bec9aab8e7d0e950df4754a1212c`、Git blob `74730241af0a9e25f0e36c2e98250f4ebbb57746`，正文及配图已目视核对。厂商要求镜头在螺纹调节范围内保留余量：完全拧入至螺纹不再可见会影响IR-CUT正常工作。它是模组机械约束，不是传感器通用寄存器事实，也不是本机已确认故障。

用户已检查无保护膜、污渍、额外透明罩，并不能证明镜头螺纹位置或IR-CUT机械动作正常。先只目视核实本机是否拧到底；不要因此自动让用户转焦环、改开关、重插排线，更不能从偏色/光晕反推出已经机械干涉。当前RAW局部笔画已见平滑过渡，温和EE/降NR无可靠收益，故该机械线索值得核对；同样不能据此跳过光学对照或宣布ISP完成。保留厂家来源、查阅日期和本机待确认状态，不把PDF原文或厂商照片打进插件包。
