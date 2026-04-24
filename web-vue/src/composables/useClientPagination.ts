import { computed, ref, watch, type Ref } from 'vue'

export const useClientPagination = <T>(items: Ref<T[]>, defaultPageSize: number) => {
  const currentPage = ref(1)
  const pageSize = ref(defaultPageSize)

  const total = computed(() => items.value.length)
  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  const paginatedItems = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return items.value.slice(start, start + pageSize.value)
  })

  const shouldPaginate = computed(() => total.value > pageSize.value)

  watch([total, pageSize], () => {
    if (currentPage.value > pageCount.value) {
      currentPage.value = pageCount.value
    }
  })

  const resetPagination = () => {
    currentPage.value = 1
  }

  return {
    currentPage,
    pageSize,
    total,
    pageCount,
    paginatedItems,
    shouldPaginate,
    resetPagination,
  }
}
