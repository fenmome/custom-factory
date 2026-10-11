<script setup lang="ts">
import { useRouter } from 'vue-router';

import { ROUTE_HOME } from '@/router';

defineOptions({ name: 'Home' });

const router = useRouter();
router.replace(ROUTE_HOME);
</script>

<template>
  <div />
</template>
