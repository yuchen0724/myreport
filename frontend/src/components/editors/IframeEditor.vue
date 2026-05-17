<template>
  <el-form label-width="100px">
    <el-form-item label="组件标题">
      <el-input v-model="form.title" placeholder="输入显示标题" />
    </el-form-item>
    <el-form-item label="嵌入 URL">
      <el-input v-model="form.url" placeholder="https://example.com" />
    </el-form-item>
  </el-form>
</template>

<script>
import { reactive, watch } from "vue"

export default {
  name: "IframeEditor",
  props: {
    widget: { type: Object, required: true },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const form = reactive({
      title: props.widget.title || "",
      url: props.widget.extra_config?.url || "",
    })

    watch(
      () => ({ ...form }),
      () => emit("update:modelValue", { ...form }),
      { deep: true }
    )

    return { form }
  },
}
</script>
