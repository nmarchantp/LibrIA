import { useId } from 'react'
import ArtworkCandle, { artworkCandles } from './ArtworkCandle'
import ArtworkLamp, { artworkLamps } from './ArtworkLamp'
import { referenceThemeArtwork } from '../theme/referenceThemeArtwork'

// Light coordinates share the illustration's 2:3 canvas and scale with it.
const lights = {
  lavanda:[[65,49,8,13]], dark:[[65,61,7,13]], otono:[[78,69,8,13]],
  invierno:[[67,44,9,14,'#b7edff']], 'rosa-antiguo':[[63,48,8,10,'#ffc7dd']],
  bosque:[[31,48,7,10]], 'dark-dorado':[[66,48,7,13],[22,96,4,7]],
  'dark-rosado':[[66.5,63,7,11]],
  'cronicas-tiempo':[[75,63,7,13]], 'reino-celestial':[[60,62,7,12]],
  'arenas-destino':[[65,62,4,8]], 'susurros-sakura':[[23,78,8,12,'#ffd5dd']],
  'archivo-galactico':[[50.5,29,10,5,'#88eaff']], 'olimpo-eterno':[[66.7,99,7,10]],
  'otono-encantado':[[69,63,8,12]], 'oraculo-luna':[[24,85,3,7],[54,57,6,7,'#d7b6ff']],
  'runas-norte':[[32,69,8,11]], 'reino-hongos':[[49,31,7,9,'#e8ff9c']],
  'catedral-cristal':[[71,65,9,19,'#c6d3ff'],[22,83,3,7]],
  'mil-una-historias':[[72,92,9,10]], 'canto-sirenas':[[46.7,48,6,10,'#ffe3b2']],
  'ecos-sombras':[[54,60,8,13],[32,77,3,6]],
  'aquelarre-medianoche':[[71.3,42,7,12]],
}
const refreshed = new Set(['lavanda','dark','otono','invierno','rosa-antiguo','bosque','dark-dorado'])
const cleanCutouts = new Set(['aquelarre-medianoche','cronicas-tiempo'])
const lanterns = new Set(['lavanda','dark','otono','invierno','rosa-antiguo','bosque','dark-dorado','dark-rosado','cronicas-tiempo','reino-celestial','susurros-sakura','otono-encantado','runas-norte','mil-una-historias','canto-sirenas','ecos-sombras','aquelarre-medianoche'])

export default function SidebarArtwork({ theme }) {
  const id=useId().replaceAll(':','')
  if(theme==='dark-blood') return null
  const candles=artworkCandles[theme] || []
  const lamp=artworkLamps[theme]
  const src=referenceThemeArtwork[theme]?.sidebar || (cleanCutouts.has(theme) ? `/images/themes/${theme}/sidebar-decoration-v2.png`
    : refreshed.has(theme) ? `/images/theme-refresh-v1/${theme}/sidebar-decoration.webp`
    : theme==='dark-rosado' ? '/images/rose-universe/rose-books-sidebar-v3.png'
      : `/images/themes/${theme}/sidebar-decoration.webp`)
  return <div className={`sidebar-artwork${lanterns.has(theme) ? ' sidebar-artwork--lantern' : ''}${lamp ? ' sidebar-artwork--lamp' : ''}`} aria-hidden="true">
    <svg className="sidebar-artwork-canvas" viewBox="0 0 100 150" preserveAspectRatio="xMidYMax meet" focusable="false">
      <defs>
        <linearGradient id={`${id}-candle-fire`} x1="0" y1="1" x2="0" y2="0"><stop stopColor="#f79429" /><stop offset=".45" stopColor="#ffc64e" /><stop offset="1" stopColor="#fff4ba" /></linearGradient>
        <radialGradient id={`${id}-candle-local-glow`}><stop stopColor="#FFCE6F" stopOpacity=".35" /><stop offset="1" stopColor="#FFAE40" stopOpacity="0" /></radialGradient>
        <radialGradient id={`${id}-candle-halo`}><stop stopColor="#ffce6f" stopOpacity=".65" /><stop offset=".4" stopColor="#ffae40" stopOpacity=".25" /><stop offset="1" stopColor="#ffae40" stopOpacity="0" /></radialGradient>
        {(lights[theme] || []).map((point,i)=><radialGradient key={i} id={`${id}-light-${i}`}>
        <stop stopColor={point[4] || '#ffe4a4'} stopOpacity=".9" /><stop offset=".35" stopColor={point[4] || '#ffe4a4'} stopOpacity=".5" /><stop offset="1" stopColor={point[4] || '#ffe4a4'} stopOpacity="0" />
      </radialGradient>)}</defs>
      <image href={src} width="100" height="150" preserveAspectRatio="xMidYMax meet" />
      {lanterns.has(theme) && (lights[theme] || []).slice(0,1).map(([cx,cy,rx,ry],i)=><g key={i} className="sidebar-lantern-glimmer">
        <ellipse cx={cx} cy={cy} rx={rx*1.9} ry={ry*1.65} fill={`url(#${id}-light-${i})`} opacity=".65" />
        <ellipse cx={cx} cy={cy} rx="1.3" ry="2.2" fill="#fff7d9" opacity=".85" />
        <path d={`M${cx} ${cy-4.5} Q${cx+.5} ${cy-.5} ${cx+3.2} ${cy} Q${cx+.5} ${cy+.5} ${cx} ${cy+4.5} Q${cx-.5} ${cy+.5} ${cx-3.2} ${cy} Q${cx-.5} ${cy-.5} ${cx} ${cy-4.5}Z`} fill="#fff6d4" opacity=".7" />
      </g>)}
      {(lights[theme] || []).map(([cx,cy,rx,ry],i)=><ellipse key={i} className="sidebar-artwork-light" cx={cx} cy={cy} rx={rx} ry={ry} fill={`url(#${id}-light-${i})`} style={{animationDelay:`${-i*.7}s`}} />)}
      {candles.map((candle,i)=><ArtworkCandle key={i} candle={candle} id={id} index={i} />)}
      {lamp && <ArtworkLamp lamp={lamp} id={id} />}
    </svg>
  </div>
}
