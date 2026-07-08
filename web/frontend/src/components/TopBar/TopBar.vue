<template>
  <div class="top-bar">
    <div class="top-bar-left">
      <!-- 移动端汉堡菜单按钮 -->
      <button v-if="isMobile" class="hamburger-btn" @click="$emit('toggle-mobile-menu')">
        ☰
      </button>
      <div class="top-bar-left-title">
        🏛️ RK3588 智能导览眼镜 - 导览目标识别管理端
      </div>
    </div>
    <div class="top-bar-right">
      <div class="device-badge">
        <span class="badge-dot"></span>
        本地演示模式
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isMobile: { type: Boolean, default: false },
});

defineEmits(["toggle-mobile-menu"]);
</script>

<style scoped lang="scss">
.top-bar {
  width: 100%;
  background: linear-gradient(135deg, #F5D5C7 0%, #E8B4A2 50%, #D4A08A 100%);
  display: flex;
  padding: 8px 0;
  height: calc(100% - 16px);
  align-items: center;
  box-shadow: 0 2px 8px rgba(180, 140, 120, 0.2);
}

.top-bar-left {
  padding-left: 24px;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 移动端汉堡按钮 */
.hamburger-btn {
  display: none;
  background: none;
  border: none;
  font-size: 24px;
  color: #5D3A2A;
  cursor: pointer;
  padding: 4px 8px;
  line-height: 1;
  border-radius: 4px;
  flex-shrink: 0;
}

.hamburger-btn:active {
  background: rgba(255, 255, 255, 0.3);
}

@media (max-width: 767px) {
  .hamburger-btn {
    display: inline-block;
  }

  .top-bar-left {
    padding-left: 12px;
  }

  .top-bar-right {
    padding-right: 12px;
  }
}

.top-bar-left-title {
  color: #5D3A2A;
  font-size: clamp(18px, 3.5vh, 36px);
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: 0.02rem;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 移动端标题允许换行 */
@media (max-width: 767px) {
  .top-bar-left-title {
    white-space: normal;
    font-size: clamp(14px, 4.5vw, 18px);
    line-height: 1.3;
  }
}

.top-bar-right {
  padding-right: 24px;
  display: flex;
  align-items: center;
}

.device-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 20px;
  background-color: rgba(255, 255, 255, 0.6);
  color: #5D3A2A;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

/* 移动端隐藏 badge 文字，只留圆点 */
@media (max-width: 480px) {
  .device-badge {
    font-size: 12px;
    padding: 6px 10px;
  }
}

.badge-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #67C23A;
  display: inline-block;
  flex-shrink: 0;
}
</style>
