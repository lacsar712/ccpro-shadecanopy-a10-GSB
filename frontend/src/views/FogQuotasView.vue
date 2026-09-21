<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const zones = ref([])
const error = ref('')
const editingId = ref(null)
const filterWorkDate = ref(todayStr())

const consumeTarget = ref(null)
const consumeError = ref('')
const consumeOk = ref('')
const consumeForm = reactive({
  minutes: 15,
  tempC: 24,
  humidityPct: 80,
  parUmol: 300,
  co2Ppm: 600,
})

function todayStr() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const form = reactive({
  zoneId: '',
  workDate: todayStr(),
  maxHours: 2,
})

const statusLabel = {
  idle: '空闲',
  growing: '在种',
  fallow: '休耕',
}

const remainingMap = computed(() => {
  const map = {}
  for (const row of list.value) {
    map[row.id] = Math.max(0, row.maxMinutes - row.usedMinutes)
  }
  return map
})

function resetForm() {
  editingId.value = null
  form.zoneId = zones.value[0]?.id || ''
  form.workDate = todayStr()
  form.maxHours = 2
}

async function loadZones() {
  const { data } = await api.get('/zones/')
  zones.value = data.results || data
  if (!form.zoneId && zones.value.length) form.zoneId = zones.value[0].id
}

async function load() {
  error.value = ''
  try {
    const params = {}
    if (filterWorkDate.value) params.workDate = filterWorkDate.value
    const { data } = await api.get('/fog-quotas/', { params })
    list.value = data.results || data
  } catch {
    error.value = '加载雾化配额失败'
  }
}

function showAll() {
  filterWorkDate.value = ''
  load()
}

function edit(row) {
  editingId.value = row.id
  form.zoneId = row.zoneId
  form.workDate = row.workDate
  form.maxHours = Number(row.maxHours)
}

async function save() {
  error.value = ''
  if (!(form.maxHours > 0)) {
    error.value = '上限小时数必须为正数'
    return
  }
  const payload = {
    zoneId: Number(form.zoneId),
    workDate: form.workDate,
    maxHours: form.maxHours,
  }
  try {
    if (editingId.value) {
      await api.put(`/fog-quotas/${editingId.value}/`, payload)
    } else {
      await api.post('/fog-quotas/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    error.value = JSON.stringify(e.response?.data || '保存失败')
  }
}

async function remove(id) {
  if (!confirm('确认删除该雾化配额？')) return
  await api.delete(`/fog-quotas/${id}/`)
  if (consumeTarget.value?.id === id) cancelConsume()
  await load()
}

function openConsume(row) {
  consumeTarget.value = row
  consumeError.value = ''
  consumeOk.value = ''
}

function cancelConsume() {
  consumeTarget.value = null
  consumeError.value = ''
  consumeOk.value = ''
}

async function consume() {
  consumeError.value = ''
  consumeOk.value = ''
  if (consumeForm.humidityPct < 70 || consumeForm.humidityPct > 95) {
    consumeError.value = '湿度 humidityPct 须在 70～95'
    return
  }
  try {
    const { data } = await api.post(`/fog-quotas/${consumeTarget.value.id}/consume/`, {
      minutes: consumeForm.minutes,
      tempC: consumeForm.tempC,
      humidityPct: consumeForm.humidityPct,
      parUmol: consumeForm.parUmol,
      co2Ppm: consumeForm.co2Ppm,
    })
    consumeOk.value =
      `消费成功：已用 ${data.quota.usedMinutes}/${data.quota.maxMinutes} 分钟，` +
      `同事务写入气候记录 #${data.climateLogId}`
    await load()
    // 面板数据以服务端重载为准,不在本地扣减
    consumeTarget.value =
      list.value.find((r) => r.id === consumeTarget.value.id) || null
  } catch (e) {
    const d = e.response?.data
    if (e.response?.status === 409 && d) {
      consumeError.value =
        d.usedMinutes !== undefined
          ? `${d.detail}：已用 ${d.usedMinutes}/${d.maxMinutes} 分钟（本次请求 ${d.requestedMinutes} 分钟）`
          : `${d.detail}（当前状态：${statusLabel[d.zoneStatus] || d.zoneStatus}）`
    } else {
      consumeError.value = JSON.stringify(d || '消费失败')
    }
  }
}

onMounted(async () => {
  await loadZones()
  await load()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>雾化配额</h1>
        <p>同区同日一条配额；消费与气候湿度写路径联锁，仅「在种」分区可消费</p>
      </div>
      <div class="actions">
        <label style="flex-direction:row;align-items:center;gap:8px">
          作业日
          <input v-model="filterWorkDate" type="date" @change="load" />
        </label>
        <button class="btn ghost" @click="showAll">全部日期</button>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑配额' : '新建配额' }}</h3>
      <div class="form-grid">
        <label>
          分区
          <select v-model="form.zoneId">
            <option v-for="z in zones" :key="z.id" :value="z.id">
              {{ z.greenhouseName }} / {{ z.zoneCode }}（{{ statusLabel[z.status] || z.status }}）
            </option>
          </select>
        </label>
        <label>作业日<input v-model="form.workDate" type="date" /></label>
        <label>上限小时数<input v-model.number="form.maxHours" type="number" step="0.5" min="0.01" /></label>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="save">保存</button>
        <button v-if="editingId" class="btn ghost" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div v-if="consumeTarget" class="panel">
      <h3 style="margin-top:0">
        消费配额：{{ consumeTarget.greenhouseName }} / {{ consumeTarget.zoneCode }}
        （{{ consumeTarget.workDate }}，已用 {{ consumeTarget.usedMinutes }}/{{ consumeTarget.maxMinutes }} 分钟）
      </h3>
      <div class="form-grid">
        <label>消费分钟<input v-model.number="consumeForm.minutes" type="number" min="1" /></label>
        <label>温度 ℃<input v-model.number="consumeForm.tempC" type="number" step="0.01" /></label>
        <label>湿度 %（70～95）<input v-model.number="consumeForm.humidityPct" type="number" step="0.01" min="70" max="95" /></label>
        <label>PAR µmol<input v-model.number="consumeForm.parUmol" type="number" step="0.01" /></label>
        <label>CO₂ ppm<input v-model.number="consumeForm.co2Ppm" type="number" step="0.01" /></label>
      </div>
      <p v-if="consumeError" class="error">{{ consumeError }}</p>
      <p v-if="consumeOk" style="color:var(--leaf-deep);margin:8px 0">{{ consumeOk }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="consume">确认消费（服务端扣减并写气候记录）</button>
        <button class="btn ghost" @click="cancelConsume">取消</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>作业日</th>
            <th>温室/分区</th>
            <th>分区状态</th>
            <th>上限小时</th>
            <th>已用/上限(分钟)</th>
            <th>剩余(分钟)</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ row.workDate }}</td>
            <td>{{ row.greenhouseName }} / {{ row.zoneCode }}</td>
            <td>
              <span class="badge" :class="row.zoneStatus">{{ statusLabel[row.zoneStatus] || row.zoneStatus }}</span>
            </td>
            <td>{{ row.maxHours }} h</td>
            <td>{{ row.usedMinutes }} / {{ row.maxMinutes }}</td>
            <td>{{ remainingMap[row.id] }}</td>
            <td class="actions">
              <button class="btn secondary" @click="openConsume(row)">消费</button>
              <button class="btn ghost" @click="edit(row)">编辑</button>
              <button class="btn danger" @click="remove(row.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!list.length">
            <td colspan="7" style="color:var(--muted)">当前筛选下暂无配额行</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
