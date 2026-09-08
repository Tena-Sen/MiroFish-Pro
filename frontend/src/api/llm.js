import service from './index'

export const getLlmConfig = () => service.get('/api/llm/config')

export const saveLlmConfig = (data) => service.post('/api/llm/config', data)

export const testLlmConnection = (data) => service.post('/api/llm/test', data)

export const getGraphBackendConfig = () => service.get('/api/llm/config')
