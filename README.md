# ShadeCanopy-01 · 分区气候日志与轮灌计划

温室「分区气候日志与轮灌计划」全栈种子项目（非考勤 OA、非库存）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python Django 5 · Django REST Framework · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端容器反代 `/api` → Django） |

## 路径与端口

- **项目路径**：`D:\work\document\bytecode\claudeCodePro\ShadeCanopy\ShadeCanopy-01\`
- **前端**：http://localhost:3500
- **后端 API**：http://localhost:8500（也可经前端同源 `/api` 访问）
- **PostgreSQL**：localhost:5435

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | admin（管理员，可进 Django Admin） |
| `grower` | `123456` | grower（种植员） |

启动时 `entrypoint.sh` 会执行 `migrate` + `seed_data` 自动写入账号与示例业务数据。
种子含雾化配额演示：在种分区各挂一条当日配额（其中一条已用满），并实际触发一次**超配额消费失败**（409 路径），日志中会打印预期失败信息；另有一条挂在空闲分区上的配额，用于演示「非在种 409」。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\ShadeCanopy\ShadeCanopy-01
docker compose up --build
```

浏览器打开 http://localhost:3500 ，使用 `grower` / `123456` 登录。

停止：

```bash
docker compose down
```

## 业务模块

1. **Auth**：JWT `POST /api/auth/token/`，当前用户 `GET /api/auth/me/`
2. **Greenhouse**：name / location / areaM2 / notes
3. **Zone**：greenhouseId / zoneCode / cropName / status(`idle|growing|fallow`)；同温室 zoneCode 唯一
4. **ClimateLog**：zoneId / recordedAt / tempC / humidityPct / parUmol / co2Ppm；**humidityPct ∈ [20, 100]**
5. **IrrigationCycle**：zoneId / startAt / durationMin / waterLiters / status(`scheduled|running|done|skipped`)
6. **FogQuota（雾化值班配额）**：zoneId / workDate / maxHours / usedMinutes(默认 0，只读)
   - 同区同日唯一（`zone + workDate`），**maxHours 必须为正数**
   - 消费接口 `POST /api/fog-quotas/{id}/consume/`：入参 `minutes / tempC / humidityPct / parUmol / co2Ppm`
   - 累计超过 `maxHours × 60` 分钟 → **409** 并回显 `usedMinutes / maxMinutes / requestedMinutes`
   - 仅「在种(`growing`)」分区允许消费；空闲(`idle`)、休耕(`fallow`)→ **409**
   - 消费成功在**同一数据库事务**内扣减配额并追加一条气候记录（**humidityPct ∈ [70, 95]**）；只改配额不写气候不算消费
7. **Dashboard**：温室数、growing 分区数、近 24h 气候日志数、今日 scheduled 轮灌数、**雾化配额日行数（fogQuotaToday，与配额表当日行数一致）** → `GET /api/dashboard/`

## API 一览

| 方法 | 路径 |
| --- | --- |
| POST | `/api/auth/token/` |
| POST | `/api/auth/token/refresh/` |
| GET | `/api/auth/me/` |
| CRUD | `/api/greenhouses/` |
| CRUD | `/api/zones/?greenhouseId=&status=` |
| CRUD | `/api/climate-logs/?zoneId=` |
| CRUD | `/api/irrigation-cycles/?zoneId=&status=` |
| CRUD | `/api/fog-quotas/?zoneId=&workDate=` |
| POST | `/api/fog-quotas/{id}/consume/` |
| GET | `/api/dashboard/` |

字段对外使用 camelCase（如 `areaM2`、`zoneCode`、`humidityPct`）。

## 本地开发（可选）

**后端**（需本机 Postgres 或已启动 compose 中的 db）：

```bash
cd backend
pip install -r requirements.txt
set POSTGRES_HOST=127.0.0.1
set POSTGRES_PORT=5435
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:8500
```

**前端**：

```bash
cd frontend
npm install
npm run dev
```

Vite 已将 `/api` 代理到 `http://127.0.0.1:8500`。

## 目录结构

```
ShadeCanopy-01/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh      # migrate + seed + gunicorn
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/            # settings / urls
│   ├── accounts/          # 自定义 User + role
│   └── core/              # 温室/分区/气候/轮灌/雾化配额 + services(消费联锁) + seed_data
└── frontend/
    ├── Dockerfile
    ├── nginx.conf         # 静态资源 + /api 反代
    ├── package.json
    └── src/               # Vue 页面（叶绿/土色主题）
```

## 配色说明

前端采用叶绿（`#3d6b3a`）与土色（`#8b6b45`）主色，米色底与侧栏深绿渐变，贴近温室场景。
