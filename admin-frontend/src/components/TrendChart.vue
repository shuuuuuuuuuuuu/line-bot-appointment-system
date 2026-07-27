<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  points: {
    type: Array,
    default: () => [],
  },
});

const SERIES = [
  {
    key: "confirmed_count",
    label: "已確認場次",
    color: "#eab308",
    axis: "left",
    format: (n) => String(n ?? 0),
  },
  {
    key: "cancelled_count",
    label: "取消／逾期",
    color: "#dc2626",
    axis: "left",
    format: (n) => String(n ?? 0),
  },
  {
    key: "revenue",
    label: "已確認營收",
    color: "#16a34a",
    axis: "right",
    format: (n) => `$${Number(n || 0).toLocaleString("zh-TW")}`,
  },
];

const enabled = ref({
  confirmed_count: true,
  cancelled_count: true,
  revenue: true,
});

const width = 720;
const height = 280;
const padding = { top: 24, right: 56, bottom: 40, left: 48 };

const activeSeries = computed(() =>
  SERIES.filter((s) => enabled.value[s.key]),
);

const maxLeft = computed(() => {
  const keys = activeSeries.value
    .filter((s) => s.axis === "left")
    .map((s) => s.key);
  if (!keys.length) return 1;
  let max = 1;
  for (const p of props.points || []) {
    for (const key of keys) {
      max = Math.max(max, Number(p[key] || 0));
    }
  }
  return max;
});

const maxRight = computed(() => {
  const keys = activeSeries.value
    .filter((s) => s.axis === "right")
    .map((s) => s.key);
  if (!keys.length) return 1;
  let max = 1;
  for (const p of props.points || []) {
    for (const key of keys) {
      max = Math.max(max, Number(p[key] || 0));
    }
  }
  return max;
});

function yFor(value, axis) {
  const innerH = height - padding.top - padding.bottom;
  const max = axis === "right" ? maxRight.value : maxLeft.value;
  return padding.top + innerH - (Number(value || 0) / max) * innerH;
}

function xFor(index, total) {
  const innerW = width - padding.left - padding.right;
  if (total <= 1) return padding.left + innerW / 2;
  return padding.left + (index / (total - 1)) * innerW;
}

const seriesPaths = computed(() => {
  const list = props.points || [];
  return activeSeries.value.map((series) => {
    const pts = list.map((p, i) => ({
      x: xFor(i, list.length),
      y: yFor(p[series.key], series.axis),
      label: p.label,
      value: Number(p[series.key] || 0),
    }));
    const path = pts
      .map((pt, i) => `${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`)
      .join(" ");
    return { ...series, pts, path };
  });
});

const leftTicks = computed(() => {
  const max = maxLeft.value;
  return [0, Math.round(max / 2), max].map((v) => ({
    value: v,
    y: yFor(v, "left"),
  }));
});

const rightTicks = computed(() => {
  const max = maxRight.value;
  return [0, Math.round(max / 2), max].map((v) => ({
    value: v,
    y: yFor(v, "right"),
    label: `$${Number(v || 0).toLocaleString("zh-TW")}`,
  }));
});

const xLabels = computed(() => {
  const list = props.points || [];
  if (!list.length) return [];
  const indexed = list.map((p, i) => ({
    label: p.label,
    x: xFor(i, list.length),
  }));
  if (indexed.length <= 8) return indexed;
  const step = Math.ceil(indexed.length / 7);
  return indexed.filter((_, i) => i % step === 0 || i === indexed.length - 1);
});

const showLeftAxis = computed(() =>
  activeSeries.value.some((s) => s.axis === "left"),
);
const showRightAxis = computed(() =>
  activeSeries.value.some((s) => s.axis === "right"),
);
</script>

<template>
  <div class="trend-chart">
    <div class="trend-chart-head">
      <h3>營運走勢</h3>
      <div class="series-toggles">
        <button
          v-for="series in SERIES"
          :key="series.key"
          type="button"
          class="series-toggle"
          :class="{ off: !enabled[series.key] }"
          @click="enabled[series.key] = !enabled[series.key]"
        >
          <i :style="{ background: series.color }" />
          {{ series.label }}
        </button>
      </div>
    </div>

    <div v-if="!points.length" class="trend-empty">此期間尚無走勢資料</div>
    <div v-else-if="!activeSeries.length" class="trend-empty">
      請至少勾選一項數據
    </div>
    <svg
      v-else
      class="trend-svg"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      aria-label="營運走勢圖"
    >
      <line
        v-for="tick in leftTicks"
        :key="`grid-${tick.value}`"
        :x1="padding.left"
        :x2="width - padding.right"
        :y1="tick.y"
        :y2="tick.y"
        class="grid-line"
      />

      <template v-if="showLeftAxis">
        <text
          v-for="tick in leftTicks"
          :key="`yl-${tick.value}`"
          :x="padding.left - 8"
          :y="tick.y + 4"
          class="axis-label"
          text-anchor="end"
        >
          {{ tick.value }}
        </text>
      </template>

      <template v-if="showRightAxis">
        <text
          v-for="tick in rightTicks"
          :key="`yr-${tick.value}`"
          :x="width - padding.right + 8"
          :y="tick.y + 4"
          class="axis-label"
          text-anchor="start"
        >
          {{ tick.label }}
        </text>
      </template>

      <g v-for="series in seriesPaths" :key="series.key">
        <path :d="series.path" class="trend-line" :stroke="series.color" />
        <circle
          v-for="(pt, i) in series.pts"
          :key="`${series.key}-dot-${i}`"
          :cx="pt.x"
          :cy="pt.y"
          r="3.2"
          :fill="series.color"
        >
          <title>{{ series.label }}｜{{ pt.label }}：{{ series.format(pt.value) }}</title>
        </circle>
      </g>

      <text
        v-for="(p, i) in xLabels"
        :key="`xl-${i}-${p.label}`"
        :x="p.x"
        :y="height - 12"
        class="axis-label"
        text-anchor="middle"
      >
        {{ p.label }}
      </text>
    </svg>
  </div>
</template>

<style scoped>
.trend-chart {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px 16px 8px;
}

.trend-chart-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.trend-chart-head h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.series-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

.series-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
}

.series-toggle.off {
  color: #94a3b8;
}

.series-toggle.off i {
  opacity: 0.35;
}

.series-toggle i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.trend-empty {
  padding: 48px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

.trend-svg {
  width: 100%;
  height: auto;
  display: block;
}

.grid-line {
  stroke: #e2e8f0;
  stroke-width: 1;
}

.axis-label {
  fill: #94a3b8;
  font-size: 11px;
}

.trend-line {
  fill: none;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
