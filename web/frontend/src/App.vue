<template>
  <div>
    <div class="top-bar-container">
      <top-bar
        :isMobile="isMobile"
        @toggle-mobile-menu="toggleMobileMenu"
      />
    </div>
    <div class="content-container">
      <!-- 移动端遮罩层 -->
      <div
        v-if="isMobile && mobileMenuOpen"
        class="mobile-overlay"
        @click="closeMobileMenu"
      ></div>

      <div
        class="side-navigation-bar-container"
        :class="{
          'sidebar-collapsed': !isMobile && sidebarCollapsed,
          'sidebar-mobile-open': isMobile && mobileMenuOpen,
          'sidebar-mobile-closed': isMobile && !mobileMenuOpen,
        }"
      >
        <side-navigation-bar
          :collapsed="!isMobile && sidebarCollapsed"
          :isMobile="isMobile"
          :mobileOpen="isMobile && mobileMenuOpen"
          @menu-click="onMenuItemClick"
          @toggle-collapse="toggleSidebarCollapse"
        />
      </div>

      <div
        class="router-view-container"
        :class="{
          'content-full': isMobile,
        }"
      >
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import SideNavigationBar from "@/components/NavigationBar/SideNavigationBar.vue";
import TopBar from "@/components/TopBar/TopBar.vue";

const BREAKPOINT = 768;

const isMobile = ref(false);
const sidebarCollapsed = ref(false);
const mobileMenuOpen = ref(false);

function checkScreenSize() {
  isMobile.value = window.innerWidth < BREAKPOINT;
  // 切换到移动端时自动关闭 mobile menu；切换到桌面端时重置相关状态
  if (!isMobile.value) {
    mobileMenuOpen.value = false;
  }
}

function toggleMobileMenu() {
  mobileMenuOpen.value = !mobileMenuOpen.value;
}

function closeMobileMenu() {
  mobileMenuOpen.value = false;
}

function toggleSidebarCollapse() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function onMenuItemClick() {
  // 移动端点击菜单项后自动关闭抽屉
  if (isMobile.value) {
    mobileMenuOpen.value = false;
  }
}

onMounted(() => {
  checkScreenSize();
  window.addEventListener("resize", checkScreenSize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", checkScreenSize);
});
</script>

<style>
*,
*::after,
*::before {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  width: 100%;
  height: 100vh;
  overflow-x: hidden;
  background-color: #FFF8F0;
}

body {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  background-color: #FFF8F0;
}

.top-bar-container {
  width: 100%;
  height: 7.5vh;
  min-height: 48px;
}

.content-container {
  display: flex;
  width: 100%;
  height: 92.5vh;
  position: relative;
}

/* ===== 桌面端侧边栏 ===== */
.side-navigation-bar-container {
  height: 100%;
  width: 220px;
  min-width: 220px;
  flex-shrink: 0;
  transition: width 0.3s ease, min-width 0.3s ease;
  overflow: hidden;
}

.side-navigation-bar-container.sidebar-collapsed {
  width: 60px;
  min-width: 60px;
}

/* ===== 路由内容区 ===== */
.router-view-container {
  flex: 1;
  height: 100%;
  overflow-y: auto;
  transition: margin-left 0.3s ease;
}

/* ===== 移动端 (<768px) ===== */
@media (max-width: 767px) {
  .side-navigation-bar-container {
    position: fixed;
    left: 0;
    top: 7.5vh;
    bottom: 0;
    z-index: 1001;
    width: 240px;
    min-width: 240px;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.15);
  }

  .side-navigation-bar-container.sidebar-mobile-open {
    transform: translateX(0);
  }

  .side-navigation-bar-container.sidebar-mobile-closed {
    transform: translateX(-100%);
  }

  .mobile-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 1000;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .router-view-container.content-full {
    margin-left: 0;
    width: 100%;
  }
}
</style>
