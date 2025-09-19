<script setup>
import { ref } from 'vue'
import TickerDashboard from './components/TickerDashboard.vue'

const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
</script>

<template>
  <div class="min-h-screen max-w-6xl mx-auto p-6 space-y-6">
    <header class="flex items-center justify-between">
      <h1 class="text-2xl md:text-3xl font-bold tracking-tight">Stock Analysis</h1>
      <a class="text-sm text-blue-600 hover:underline" href="https://github.com/" target="_blank">GitHub</a>
    </header>
    <TickerDashboard />
  </div>
</template>
