<script setup>
import { computed } from "vue";

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  title: {
    type: String,
    default: "阿卡西項目分析",
  },
});

const maxCount = computed(() =>
  Math.max(1, ...(props.items || []).map((i) => Number(i.booking_count || 0))),
);

const totalCount = computed(() =>
  (props.items || []).reduce((sum, i) => sum + Number(i.booking_count || 0), 0),
);

const chartHeight = computed(() => {
  const rows = Math.max((props.items || []).length, 1);
  return Math.max(180, 36 + rows * 34);
});

const width = 720;
const padding = { top: 16, right: 56, bottom: 16, left: 168 };

const bars = computed(() => {
  const list = props.items || [];
  const innerW = width - padding.left - padding.right;
  const rowH = 34;
  return list.map((item, i) => {
    const count = Number(item.booking_count || 0);
    const barW = (count / maxCount.value) * innerW;
    const y = padding.top + i * rowH;
    return {
      name: item.service_name,
      count,
      y,
      barW: Math.max(barW, count > 0 ? 4 : 0),
      labelX: padding.left + Math.max(barW, 0) + 8,
      percent:
        totalCount.value > 0
          ? Math.round((count / totalCount.value) * 100)
          : 0,
    };
  });
});
</script>

<template>
  <div class="service-bar-chart">
    <div class="chart-head">
      <h3>{{ title }}</h3>
      <span class="chart-meta">已確認預約中的選項次數（可複選）</span>
    </div>

    <div v-if="!items.length" class="chart-empty">尚無阿卡西服務項目</div>
    <div v-else-if="totalCount === 0" class="chart-empty">
      此期間尚無已確認的阿卡西預約
    </div>
    <svg
      v-else
      class="chart-svg"
      :viewBox="`0 0 ${width} ${chartHeight}`"
      role="img"
      :aria-label="title"
    >
      <g v-for="(bar, i) in bars" :key="`${bar.name}-${i}`">
        <text
          :x="padding.left - 12"
          :y="bar.y + 16"
          class="name-label"
          text-anchor="end"
        >
          {{ bar.name }}
        </text>
        <rect
          :x="padding.left"
          :y="bar.y + 4"
          :width="bar.barW"
          height="18"
          rx="4"
          class="bar"
        />
        <text :x="bar.labelX" :y="bar.y + 17" class="value-label">
          {{ bar.count }}（{{ bar.percent }}%）
        </text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.service-bar-chart {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px 16px 10px;
}

.chart-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.chart-head h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.chart-meta {
  color: #94a3b8;
  font-size: 12px;
}

.chart-empty {
  padding: 40px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

.chart-svg {
  width: 100%;
  height: auto;
  display: block;
}

.name-label {
  fill: #475569;
  font-size: 12px;
}

.value-label {
  fill: #64748b;
  font-size: 12px;
}

.bar {
  fill: #16a34a;
}
</style>
