import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

export const useAppStore = defineStore('app', () => {
  /** 侧边栏是否折叠 */
  const siderCollapse = ref(false);

  /** 是否为移动端布局 */
  const isMobile = ref(false);

  /** 是否全屏 */
  const fullContent = ref(false);

  /** 是否显示重载抽屉 */
  const reloadFlag = ref(true);

  const contentPadding = computed(() => (isMobile.value ? '12px' : '16px'));

  function toggleSiderCollapse() {
    siderCollapse.value = !siderCollapse.value;
  }

  function setIsMobile(mobile: boolean) {
    isMobile.value = mobile;
  }

  async function reloadPage(duration = 300) {
    reloadFlag.value = false;
    await new Promise(resolve => {
      setTimeout(resolve, duration);
    });
    reloadFlag.value = true;
  }

  return {
    siderCollapse,
    isMobile,
    fullContent,
    reloadFlag,
    contentPadding,
    toggleSiderCollapse,
    setIsMobile,
    reloadPage
  };
});
