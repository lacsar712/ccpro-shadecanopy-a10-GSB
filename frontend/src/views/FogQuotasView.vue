<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const zones = ref([])
const error = ref('')
const consumeMsg = ref('')
const consumeError = ref('')
const editingId = ref(null)
const filterDate = ref(todayInputValue())

const zoneStatusLabel = {
  idle: '空闲',
  growing: '在种',
  fallow: '休耕',
}

function todayInputValue(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const form = reactive({
  zoneId: '',
  workDate: todayInputValue(),
  maxHours: 2,
})

const consumeForm = reactive({
  quotaId: '',
  minutes: 15,
  humidityPct: 85,
  tempC: 25,
})

const consumableList = computed(() =>
  list.value.filter((q) => q.zoneStatus === 'growing' && q.usedMinutes < q.maxMinutes)
)

function resetForm() {
  editingId.value = null
  form.zoneId = zones.value[0]?.id || ''
  form.workDate = todayInputValue()
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
    if (filterDate.value) params.workDate = filterDate.value
    const { data } = await api.get('/fog-quotas/', { params })
    list.value = data.results || data
    if (!consumeForm.quotaId && consumableList.value.length) {
      consumeForm.quotaId = consumableList.value[0].id
    }
  } catch {
    error.value = '加载雾化配额失败'
  }
}

function showAll() {
  filterDate.value = ''
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
  await load()
}

// 消费一律提交后端：配额扣减与气候记录由后端在同一事务完成，
// 前端不在本地扣减已用分钟。
async function consume() {
  consumeMsg.value = ''
  consumeError.value = ''
  if (!consumeForm.quotaId) {
    consumeError.value = '请选择要消费的配额'
    return
  }
  if (consumeForm.humidityPct < 70 || consumeForm.humidityPct > 95) {
    consumeError.value = '湿度 humidityPct 须在 70～95'
    return
  }
  try {
    const { data } = await api.post(`/fog-quotas/${consumeForm.quotaId}/consume/`, {
      minutes: consumeForm.minutes,
      humidityPct: consumeForm.humidityPct,
      tempC: consumeForm.tempC,
    })
    consumeMsg.value = `消费成功：已用 ${data.usedMinutes} 分钟，同事务写入气候记录 #${data.climateLogId}`
    await load()
  } catch (e) {
    const body = e.response?.data
    if (e.response?.status === 409 && body) {
      consumeError.value = `${body.detail}（已用 ${body.usedMinutes} 分钟${
        body.maxMinutes != null ? ` / 上限 ${body.maxMinutes} 分钟` : ''
      }${body.zoneStatus ? `，分区状态：${zoneStatusLabel[body.zoneStatus] || body.zoneStatus}` : ''}）`
    } else {
      consumeError.value = JSON.stringify(body || '消费失败')
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
        <p>按分区 + 作业日限制雾化时长；消费与气候湿度记录同库事务联锁</p>
      </div>
      <div class="actions">
        <input v-model="filterDate" type="date" @change="load" />
        <button class="btn ghost" @click="showAll">全部</button>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑配额' : '新建配额' }}</h3>
      <div class="form-grid">
        <label>
          分区
          <select v-model="form.zoneId">
            <option v-for="z in zones" :key="z.id" :value="z.id">
              {{ z.greenhouseName }} / {{ z.zoneCode }}（{{ zoneStatusLabel[z.status] || z.status }}）
            </option>
          </select>
        </label>
        <label>作业日<input v-model="form.workDate" type="date" /></label>
        <label>上限小时数<input v-model.number="form.maxHours" type="number" step="0.5" min="0.5" /></label>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="save">保存</button>
        <button v-if="editingId" class="btn ghost" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">配额消费</h3>
      <div class="form-grid">
        <label>
          配额（在种且未满额）
          <select v-model="consumeForm.quotaId">
            <option v-for="q in consumableList" :key="q.id" :value="q.id">
              {{ q.workDate }} · {{ q.greenhouseName }} / {{ q.zoneCode }}（已用 {{ q.usedMinutes }}/{{ q.maxMinutes }} 分）
            </option>
          </select>
        </label>
        <label>消费分钟<input v-model.number="consumeForm.minutes" type="number" min="1" /></label>
        <label>湿度 %（70～95）<input v-model.number="consumeForm.humidityPct" type="number" step="0.01" min="70" max="95" /></label>
        <label>温度 ℃<input v-model.number="consumeForm.tempC" type="number" step="0.01" /></label>
      </div>
      <p v-if="consumeError" class="error">{{ consumeError }}</p>
      <p v-if="consumeMsg" class="success">{{ consumeMsg }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="consume">提交消费</button>
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
            <th>已用 / 上限(分)</th>
            <th>剩余(分)</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ row.workDate }}</td>
            <td>{{ row.greenhouseName }} / {{ row.zoneCode }}</td>
            <td>
              <span class="badge" :class="row.zoneStatus">{{ zoneStatusLabel[row.zoneStatus] || row.zoneStatus }}</span>
            </td>
            <td>{{ row.maxHours }} h</td>
            <td>{{ row.usedMinutes }} / {{ row.maxMinutes }}</td>
            <td>{{ row.maxMinutes - row.usedMinutes }}</td>
            <td class="actions">
              <button class="btn ghost" @click="edit(row)">编辑</button>
              <button class="btn danger" @click="remove(row.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
