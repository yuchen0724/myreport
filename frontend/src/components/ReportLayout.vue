<template>
  <div class="report-layout" :class="{ 'edit-mode': isEditing }">
    <grid-layout
      :layout.sync="layoutItems"
      :col-num="12"
      :row-height="rowHeight"
      :is-draggable="isEditing"
      :is-resizable="isEditing"
      :is-mirrored="false"
      :vertical-compact="true"
      :margin="[12, 12]"
      :use-css-transforms="true"
    >
      <grid-item
        v-for="item in layoutItems"
        :key="item.i"
        :x="item.x"
        :y="item.y"
        :w="item.w"
        :h="item.h"
        :i="item.i"
        :min-w="2"
        :min-h="2"
        class="grid-item"
        :class="{ 'grid-item-editing': isEditing }"
      >
        <WidgetSlot
          :widget="item"
          :type="item.widget_type"
          :subtype="item.widget_subtype"
          :title="item.title"
          :is-editing="isEditing"
          :dashboard-data="dashboardData"
          :extra-config="item.extra_config"
          @edit="$emit('editWidget', item)"
          @remove="$emit('removeWidget', item)"
          @drillDown="$emit('drillDown', $event)"
        />
      </grid-item>
    </grid-layout>
  </div>
</template>

<script>
import { GridLayout, GridItem } from "grid-layout-plus"
import "grid-layout-plus/es/index.mjs" // 样式随模块加载
import WidgetSlot from "./WidgetSlot.vue"

export default {
  name: "ReportLayout",
  components: { GridLayout, GridItem, WidgetSlot },
  props: {
    layoutItems: { type: Array, required: true },
    isEditing: { type: Boolean, default: false },
    rowHeight: { type: Number, default: 100 },
    dashboardData: { type: Object, default: () => ({}) },
  },
  emits: ["update:layoutItems", "editWidget", "removeWidget", "drillDown"],
  setup(props, { emit }) {
    // grid-layout-plus 的 layout.sync 要求 layout 可响应式
    // 父组件通过 v-model:layoutItems 绑定
    return {}
  },
}
</script>

<style scoped>
.report-layout {
  width: 100%;
  min-height: 400px;
}
.grid-item {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.grid-item:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}
.grid-item-editing {
  border-color: #409eff;
  border-style: dashed;
}
.edit-mode .grid-item-editing:hover {
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.2);
}
</style>
