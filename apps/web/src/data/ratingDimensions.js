import { Droplets, Footprints, Ghost, Heart, Laugh, RefreshCw, Snail, Star, Swords, Zap } from 'lucide-react'
import SpicyRatingIcon from '../components/SpicyRatingIcon'
import WorldBuildingRatingIcon from '../components/WorldBuildingRatingIcon'

export const ratingDimensions = [
  ['general', 'General', Star, undefined, '#F6D76B', '#A78020'], ['plot_twist', 'Plot twist', RefreshCw, undefined, '#B68AF5', '#7041A8'],
  ['tears', 'Lágrimas', Droplets, undefined, '#75D4F5', '#24799D'], ['romance', 'Romance', Heart, undefined, '#F16A8C', '#A52750'],
  ['spicy', 'Spicy', SpicyRatingIcon, undefined, '#FF893D', '#A83D10'], ['action', 'Acción', Zap, undefined, '#D6A12E', '#865D0A'],
  ['world_building', 'World building', WorldBuildingRatingIcon, undefined, '#67C98B', '#26784A'], ['pace', 'Ritmo', Footprints, undefined, '#568FE5', '#244F9A'],
  ['battles', 'Batallas', Swords, '1 de 5: pocas batallas o poco protagonismo. 5 de 5: batallas muy presentes o intensas.', '#A9B0BB', '#59616E'],
  ['horror', 'Terror', Ghost, '1 de 5: casi nada de miedo. 5 de 5: terror muy intenso.', '#F5F5F5', '#888888'],
  ['boring_moments', 'Momentos aburridos', Snail, '1 de 5: casi ningún momento aburrido. 5 de 5: muchos momentos aburridos.', '#D7BE9D', '#826343'],
  ['comedy', 'Comedia', Laugh, '1 de 5: poco humor. 5 de 5: mucho humor.', '#E8E34D', '#77710C'],
]

export const ratingDimensionLabels = Object.fromEntries(ratingDimensions.map(([key, label]) => [key, label]))
