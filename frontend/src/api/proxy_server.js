import axios from '@/utils/request'

export const getProxyServerList = () => axios.get('/proxy-servers')

export const getProxyServer = (id) => axios.get(`/proxy-servers/${id}`)

export const createProxyServer = (data) => axios.post('/proxy-servers', data)

export const updateProxyServer = (id, data) => axios.put(`/proxy-servers/${id}`, data)

export const deleteProxyServer = (id) => axios.delete(`/proxy-servers/${id}`)

export const testProxyServer = (data) => axios.post('/proxy-servers/test', data)

export const getActiveProxyServers = () => axios.get('/proxy-servers/active')