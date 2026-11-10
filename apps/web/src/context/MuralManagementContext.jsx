import { createContext, useContext } from 'react'
export const MuralManagementContext=createContext(null)
export const useMuralManagement=()=>useContext(MuralManagementContext)
