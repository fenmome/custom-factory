import { onMounted, onUnmounted, ref } from 'vue';

/** 轮询 Hook：每隔 ms 执行一次回调，页面卸载自动清理。 */
export function usePolling(fn: () => void | Promise<void>, ms = 10_000, immediate = false) {
  const timer = ref<ReturnType<typeof setInterval> | null>(null);
  const running = ref(false);

  async function tick() {
    if (running.value) return;
    running.value = true;
    try {
      await fn();
    } finally {
      running.value = false;
    }
  }

  function start() {
    if (timer.value) return;
    timer.value = setInterval(tick, ms);
  }

  function stop() {
    if (timer.value) {
      clearInterval(timer.value);
      timer.value = null;
    }
  }

  onMounted(() => {
    if (immediate) void tick();
    start();
  });

  onUnmounted(stop);

  return { tick, start, stop, running };
}

/** 布尔状态 Hook。 */
export function useBoolean(initial = false) {
  const bool = ref(initial);
  function setTrue() {
    bool.value = true;
  }
  function setFalse() {
    bool.value = false;
  }
  function toggle() {
    bool.value = !bool.value;
  }
  return { bool, setTrue, setFalse, toggle };
}

/** 表格分页 Hook。 */
export function useTablePagination(options: { defaultPageSize?: number } = {}) {
  const page = ref(1);
  const pageSize = ref(options.defaultPageSize ?? 20);
  const total = ref(0);

  function reset() {
    page.value = 1;
  }

  return { page, pageSize, total, reset };
}
