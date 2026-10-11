<script setup lang="ts">
import { Lock, Message, View } from '@element-plus/icons-vue';
import { ElMessage, type FormInstance, type FormRules } from 'element-plus';
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/store/modules/auth';

defineOptions({ name: 'Login' });

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const formRef = ref<FormInstance>();
const loading = ref(false);
const remember = ref(true);

/** 仅本地开发展示种子账号，避免“不知道用哪个账号登录”。 */
const isDev = import.meta.env.DEV;
const devAccount = { email: 'admin@custom-factory.com', password: 'Admin@123456' };

const model = reactive<Api.Auth.LoginParams>({
  email: '',
  password: ''
});

const rules: FormRules<Api.Auth.LoginParams> = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }]
};

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  loading.value = true;
  try {
    const result = await auth.login(model);
    if (!result.success) {
      ElMessage.error(result.error);
      return;
    }
    ElMessage.success('登录成功');
    const redirect = (route.query.redirect as string) || '/dashboard/overview';
    router.replace(redirect);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login">
    <div class="login__panel">
      <div class="login__intro">
        <div class="login__logo">CF</div>
        <h1 class="login__title">Custom Factory</h1>
        <p class="login__desc">定制商品生产系统 · 批次 / SKU / 图片 / 质检全流程管控</p>
        <ul class="login__points">
          <li>八槽位图片流水线，全部自动或手工接入同一接收校验</li>
          <li>技术质检不可人工放行，语义结果由人工最终裁定</li>
          <li>三色生产保护 + 最小影响范围暂停 + 试运行恢复</li>
        </ul>
      </div>

      <div class="login__form">
        <h2>登录</h2>
        <el-form ref="formRef" :model="model" :rules="rules" label-position="top" size="large" @keyup.enter="submit">
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="model.email" :prefix-icon="Message" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="model.password"
              type="password"
              show-password
              :prefix-icon="Lock"
              placeholder="请输入密码"
            />
          </el-form-item>
          <div class="login__row">
            <el-checkbox v-model="remember">记住我</el-checkbox>
            <span class="cf-muted">忘记密码请联系管理员（Owner）</span>
          </div>
          <el-button type="primary" size="large" :loading="loading" class="login__submit" @click="submit">登 录</el-button>
        </el-form>
        <el-alert
          v-if="isDev"
          class="login__hint"
          type="info"
          :closable="false"
          title="本地开发账号"
          :description="`${devAccount.email} / ${devAccount.password}`"
        />
        <p class="login__tip cf-muted">
          <el-icon><View /></el-icon>
          生产环境凭证由管理员分配，请勿共享账号
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.login {
  display: flex;
  height: 100vh;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 20% 20%, #2a3358 0%, #1d2233 45%, #15192a 100%);

  &__panel {
    display: flex;
    width: min(960px, 92vw);
    min-height: 480px;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 24px 60px rgb(0 0 0 / 35%);
    background-color: #fff;
  }

  &__intro {
    display: flex;
    width: 42%;
    flex-direction: column;
    justify-content: center;
    gap: 12px;
    padding: 40px 36px;
    color: #fff;
    background: linear-gradient(150deg, #3b52d8, #6b46e5 60%, #8b5cf6);
  }

  &__logo {
    display: flex;
    width: 44px;
    height: 44px;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    background: rgb(255 255 255 / 18%);
    font-weight: 700;
  }

  &__title {
    margin: 0;
    font-size: 26px;
  }

  &__desc {
    margin: 0;
    font-size: 13px;
    opacity: 0.85;
  }

  &__points {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 13px;
    opacity: 0.9;

    li::before {
      content: '✓ ';
    }
  }

  &__form {
    display: flex;
    width: 58%;
    flex-direction: column;
    justify-content: center;
    padding: 44px 48px;

    h2 {
      margin: 0 0 20px;
      font-size: 22px;
    }
  }

  &__row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 18px;
  }

  &__submit {
    width: 100%;
  }

  &__tip {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 16px;
  }
}
</style>
