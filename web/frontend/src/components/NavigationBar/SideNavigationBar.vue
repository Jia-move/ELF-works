<template>
  <div
    class="side-navigation-bar"
    :class="{ 'nav-collapsed': collapsed, 'nav-mobile': isMobile }"
  >
    <!-- 桌面端：折叠按钮 -->
    <div v-if="!isMobile" class="collapse-toggle" @click="$emit('toggle-collapse')">
      <span class="collapse-icon">{{ collapsed ? '▶' : '◀' }}</span>
    </div>

    <div class="nav-header" v-show="!collapsed || isMobile">
      <div class="nav-logo">📱</div>
      <div class="nav-title">导航菜单</div>
    </div>

    <!-- 折叠模式下的 logo -->
    <div v-if="collapsed && !isMobile" class="nav-header-collapsed">
      <div class="nav-logo-small">📱</div>
    </div>

    <div
      class="option"
      v-for="item in options"
      :key="item.id"
      @click="handleMenuClick(item)"
      :class="selectId === item.id ? 'selected' : ''"
      :title="collapsed && !isMobile ? item.content : ''"
    >
      <span class="option-icon">{{ item.icon }}</span>
      <div class="option-text" v-show="!collapsed || isMobile">
        {{ item.content }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";

defineProps({
  collapsed: { type: Boolean, default: false },
  isMobile: { type: Boolean, default: false },
  mobileOpen: { type: Boolean, default: false },
});

const emit = defineEmits(["menu-click", "toggle-collapse"]);

const router = useRouter();
const route = useRoute();

const selectId = ref(0);

const options = ref([
  {
    id: 0,
    content: "系统总览",
    icon: "📊",
    path: "/dashboard",
  },
  {
    id: 1,
    content: "导览识别记录",
    icon: "📷",
    path: "/recognitions",
  },
  {
    id: 2,
    content: "导览内容库",
    icon: "📚",
    path: "/scenic-spots",
  },
  {
    id: 3,
    content: "智能问答记录",
    icon: "💬",
    path: "/qa-records",
  },
  {
    id: 4,
    content: "设备管理",
    icon: "🖥️",
    path: "/devices",
  },
]);

const handleMenuClick = (item) => {
  pushRouterPath(item);
  emit("menu-click");
};

const pushRouterPath = (item) => {
  router.push(item.path);
  selectId.value = item.id;
};

const reloadSelectId = () => {
  const selected_path = route.path;
  const index = options.value.findIndex(
    (option) => option.path === selected_path
  );
  if (index !== -1) {
    selectId.value = index;
  }
};

onMounted(() => {
  reloadSelectId();
  router.afterEach((to) => {
    const path = to.path;
    const index = options.value.findIndex((option) => option.path === path);
    if (index !== -1) {
      selectId.value = index;
    }
  });
});
</script>

<style scoped>
.side-navigation-bar {
  padding-top: 16px;
  height: 100%;
  width: 100%;
  font-size: clamp(14px, 1.6vw, 18px);
  color: #5D3A2A;
  background-color: #FFF5EE;
  border-right: 1px solid #F0D5C0;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ===== 折叠切换按钮（仅桌面端可见） ===== */
.collapse-toggle {
  display: flex;
  justify-content: flex-end;
  padding: 4px 14px 8px 14px;
  cursor: pointer;
  user-select: none;
}

.collapse-icon {
  font-size: 12px;
  color: #B8653A;
  transition: transform 0.3s ease;
}

.collapse-toggle:hover .collapse-icon {
  color: #E8A87C;
}

/* 折叠模式：导航仅保留图标 */
.nav-collapsed .option {
  justify-content: center;
  padding: 14px 0;
  margin: 4px 8px;
}

.nav-collapsed .option-icon {
  margin: 0;
}

/* ===== 折叠模式小 logo ===== */
.nav-header-collapsed {
  display: flex;
  justify-content: center;
  padding: 8px 0 16px 0;
  border-bottom: 1px solid #F0D5C0;
  margin-bottom: 8px;
}

.nav-logo-small {
  font-size: 22px;
}

/* ===== 导航头部 ===== */
.nav-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px 20px 20px;
  border-bottom: 1px solid #F0D5C0;
  margin-bottom: 8px;
}

.nav-logo {
  font-size: 24px;
}

.nav-title {
  font-size: 16px;
  font-weight: 600;
  color: #8B6B5A;
}

/* ===== 菜单项 ===== */
.option {
  width: calc(100% - 20px);
  height: auto;
  padding: 12px 0 12px 20px;
  margin: 4px 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.option:hover {
  background-color: #FDE8D5;
}

.option.selected {
  color: #B8653A;
  background-color: #FDE0CC;
  font-weight: 600;
}

.option-icon {
  font-size: 18px;
  width: 28px;
  text-align: center;
  flex-shrink: 0;
}

.option-text {
  margin-left: 10px;
  white-space: nowrap;
}
</style>
