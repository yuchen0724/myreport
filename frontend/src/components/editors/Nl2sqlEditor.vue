<template>
  <el-form label-width="100px">
    <el-form-item label="组件标题">
      <el-input v-model="form.title" placeholder="输入显示标题" />
    </el-form-item>
  </el-form>
</template>

<script>
import { reactive, watch } from "vue"

export default {
  name: "Nl2sqlEditor",
  props: {
    widget: { type: Object, required: true },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const form = reactive({
      title: props.widget.title || "",
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
