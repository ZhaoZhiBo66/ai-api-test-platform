# 分页查询接口 JMeter 基线练习

这个目录提供一个只读性能测试脚本：

```text
interface_page_baseline.jmx
```

它请求：

```http
GET /interfaces/page?page=1&page_size=20
X-API-Key: ...
```

脚本不会新增、修改或删除平台数据。默认的10个用户、60秒和单次响应1000ms，只是本地练习参数，不是已经验证的性能结果，也不是生产SLA。

## 1. 运行前检查

1. 安装与你所用JMeter版本兼容的Java，并确认 `java -version` 可以执行。
2. 确认 `jmeter --version` 可以执行。
3. 启动AI接口自动化平台。
4. 确认 `http://127.0.0.1:8000/health` 返回200。
5. 如果平台启用了API Key认证，准备一个只用于本地或测试环境的Key。

当前电脑能够找到JMeter启动器，但Java尚未正确安装或配置，因此补齐Java环境前不能生成真实JMeter结果。

## 2. 准备本地参数

复制示例配置：

```powershell
Copy-Item performance/local.properties.example performance/local.properties
```

编辑 `performance/local.properties`。如果启用了认证，填写本地测试Key；不要使用生产密钥，也不要提交这个文件。

主要参数：

| 参数 | 含义 | 默认值 |
|---|---|---:|
| `threads` | 虚拟用户数 | 10 |
| `ramp_up` | 启动全部用户所需秒数 | 10 |
| `duration` | 稳定执行秒数 | 60 |
| `page_size` | 分页大小，接口允许5至100 | 20 |
| `think_time_ms` | 每次请求前等待时间 | 200 |
| `max_response_ms` | 单次响应练习阈值 | 1000 |

## 3. 先做单用户调试

先确认脚本、认证和断言都正确：

```powershell
jmeter -n -t performance/interface_page_baseline.jmx -q performance/local.properties -Jthreads=1 -Jramp_up=1 -Jduration=10 -l performance/results/debug.jtl
```

必须先检查：

- 没有401或连接失败。
- HTTP状态码为200。
- 响应包含 `items`、`total`、`page`、`page_size` 和 `pages`。
- JMeter没有把功能错误误算成性能结果。

## 4. 执行第一轮基线

先创建结果父目录，再为每次运行使用新的目录名：

```powershell
New-Item -ItemType Directory -Force performance/results, performance/reports
$run_id = Get-Date -Format "yyyyMMdd-HHmmss"
jmeter -n -t performance/interface_page_baseline.jmx -q performance/local.properties -l "performance/results/$run_id.jtl" -e -o "performance/reports/$run_id"
```

JMeter要求HTML报告输出目录不存在或为空，所以每次使用新的时间戳目录，不覆盖旧报告。

正式加压时不要打开“查看结果树”保存所有响应，因为监听器本身可能消耗大量内存。

## 5. 逐步加压

不要一开始直接使用几百个用户。建议依次执行并记录：

| 阶段 | 用户数 | Ramp-up | 持续时间 | 目的 |
|---|---:|---:|---:|---|
| 脚本校验 | 1 | 1秒 | 10秒 | 验证请求与断言 |
| 本地基线 | 10 | 10秒 | 60秒 | 得到第一份可比较结果 |
| 小负载 | 25 | 25秒 | 5分钟 | 观察趋势 |
| 较高负载 | 50 | 50秒 | 5分钟 | 寻找本机环境瓶颈 |

后一阶段只有在前一阶段错误率可接受、客户端和服务端资源没有失控时才继续。以上数字仅用于学习，不能代替业务容量目标。

## 6. 报告必须记录

- 测试时间、代码版本、环境和机器配置。
- 线程数、Ramp-up、持续时间、思考时间和测试数据量。
- 总请求数、吞吐量、错误率。
- 平均响应时间、P90、P95、P99和最大响应时间。
- 应用CPU、内存、线程或Worker状态。
- MySQL连接、慢SQL、锁等待和资源使用情况。
- 失败类型以及对应日志证据。
- 是否满足预先定义的目标。

不要只保存一张JMeter聚合报告截图，也不要只写“接口性能良好”。

## 7. 结果解释边界

- 本地电脑结果只能作为本地基线，不能直接代表生产容量。
- 如果压测机CPU或内存先达到上限，测试结果反映的可能是压测机瓶颈。
- 默认的1000ms是练习断言，不是业务SLA。
- 当前脚本只覆盖分页查询，不代表整个平台已经完成性能测试。
- 结果中出现401、断言失败或大量连接错误时，应先修复功能和环境问题，再讨论性能。
