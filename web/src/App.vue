<script>
import { RouterView } from 'vue-router';
</script>

<template>
  <div class="router_links">
    <router-link to="/">Home</router-link>
    <router-link to="/rag">RAG</router-link>
  </div>
  <div class="router_container">
    <RouterView></RouterView>
  </div>
</template>

<style scoped>
.router_links{
  position: relative;
  width: 100%;
  height: 30px;
  box-sizing: border-box;
  padding: 5px;
  margin: 0;
  border-bottom: 1px solid #ccc;
}

.router_links a{
  margin-right: 10px;
}

.router_container{
  position: relative;
  width: 100%;
  height: calc(100% - 30px);
  box-sizing: border-box;
  padding: 5px;
  margin: 0;
}
</style>
