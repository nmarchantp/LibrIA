import { useId } from 'react'
import TasteIcon from './TasteIcon'
import './ProfileReadingTastesCard.css'

const colors = new Set(['affection', 'warmth', 'mystic', 'energy', 'calm'])
export default function IntensityIndicator({ option, level, onChange, disabled }) {
  const name = useId()
  const description = option.levels[level - 1]
  return <div className={`reader-intensity reader-intensity--${colors.has(option.color) ? option.color : 'mystic'}`}>
    {onChange ? <fieldset className="reader-intensity-scale" disabled={disabled}>
      <legend className="reader-visually-hidden">Intensidad de {option.name}</legend>
      {[1, 2, 3, 4, 5].map(value => <label key={value} className={value <= level ? 'is-filled' : ''}>
        <input type="radio" name={name} value={value} checked={level === value} onChange={() => onChange(value)} aria-label={`${option.name}: ${value} de 5. ${option.levels[value - 1]}`} />
        <TasteIcon name={option.icon} size={21} aria-hidden="true" />
      </label>)}
    </fieldset> : <div className="reader-intensity-scale" aria-hidden="true">{[1, 2, 3, 4, 5].map(value => <span className={value <= level ? 'is-filled' : ''} key={value}><TasteIcon name={option.icon} size={21} /></span>)}</div>}
    <p className="reader-intensity-description">{level}/5 · {description}</p>
  </div>
}

