import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createProject, deleteProject, listProjects, type ProjectSummary } from '../api'

/** 项目列表与创建（R1 / R5）。 */
export const useProjectsStore = defineStore('projects', () => {
  const projects = ref<ProjectSummary[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchList(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      projects.value = await listProjects()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      loading.value = false
    }
  }

  function create(prompt: string): Promise<{ id: number; title: string }> {
    return createProject(prompt)
  }

  async function remove(id: number): Promise<void> {
    await deleteProject(id)
    projects.value = projects.value.filter((p) => p.id !== id)
  }

  return { projects, loading, error, fetchList, create, remove }
})
