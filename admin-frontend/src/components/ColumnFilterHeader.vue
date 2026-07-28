<script setup>
import { computed } from "vue";
import { Filter } from "@element-plus/icons-vue";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  options: {
    type: Array,
    default: () => [],
  },
  modelValue: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["update:modelValue"]);

const isActive = computed(() => (props.modelValue || []).length > 0);

function onChange(values) {
  emit("update:modelValue", values);
}
</script>

<template>
  <div class="column-filter-header" @click.stop>
    <span class="column-filter-label">{{ label }}</span>
    <el-popover
      placement="bottom-start"
      :width="200"
      trigger="click"
      :show-arrow="false"
      popper-class="appointment-column-filter-popper"
    >
      <template #reference>
        <button
          type="button"
          class="filter-trigger"
          :class="{ active: isActive }"
          aria-label="篩選"
        >
          <el-icon :size="14"><Filter /></el-icon>
        </button>
      </template>

      <el-checkbox-group
        class="filter-checks"
        :model-value="modelValue"
        @update:model-value="onChange"
      >
        <el-checkbox
          v-for="opt in options"
          :key="String(opt.value)"
          :value="opt.value"
        >
          {{ opt.label }}
        </el-checkbox>
      </el-checkbox-group>
      <p v-if="!options.length" class="filter-empty">無可篩選項目</p>
    </el-popover>
  </div>
</template>

<style scoped>
.column-filter-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  line-height: 1;
}

.column-filter-label {
  font-weight: 600;
}

.filter-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  background: transparent;
  color: #c0c4cc;
  cursor: pointer;
  vertical-align: middle;
}

.filter-trigger:hover,
.filter-trigger.active {
  color: var(--el-color-primary);
}

.filter-checks {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow: auto;
  padding: 4px 0;
}

.filter-checks :deep(.el-checkbox) {
  margin-right: 0;
  height: auto;
  white-space: normal;
}

.filter-empty {
  margin: 0;
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
}
</style>
