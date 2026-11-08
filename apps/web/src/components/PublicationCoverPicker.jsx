import { useEffect, useId, useMemo, useState } from 'react'
import { Camera, ImagePlus, X } from 'lucide-react'
import './PublicationCoverPicker.css'

export default function PublicationCoverPicker({ mode, onModeChange, file, onChange, currentUrl, catalogUrl, disabled = false }) {
  const id = useId()
  const [error, setError] = useState('')
  const preview = useMemo(()=>file ? URL.createObjectURL(file) : null,[file])
  useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview)},[preview])
  function choose(event) {
    const value=event.target.files?.[0]
    event.target.value=''
    if(!value)return
    if(!['image/jpeg','image/png','image/webp','image/gif'].includes(value.type)) {setError('Usa JPEG, PNG, GIF o WebP.');return}
    if(value.size>5*1024*1024) {setError('La portada admite hasta 5 MB.');return}
    setError('');onModeChange('custom');onChange(value)
  }
  const image=mode==='custom' ? preview||currentUrl : catalogUrl
  return <fieldset className="publication-cover-picker" disabled={disabled}>
    <legend>Imagen de la obra en esta publicación</legend>
    <div className="publication-cover-options"><label><input type="radio" name={id} checked={mode==='catalog'} onChange={()=>{onModeChange('catalog');onChange(null);setError('')}} />Usar portada del catálogo</label><label><input type="radio" name={id} checked={mode==='custom'} onChange={()=>onModeChange('custom')} />Subir imagen propia</label></div>
    {mode==='custom' && <div className="publication-cover-upload">
      {image&&<img src={image} alt="Vista previa de la portada personalizada" />}
      <div><label className="publication-cover-file"><ImagePlus size={16} />{file||currentUrl?'Cambiar imagen':'Elegir imagen'}<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={choose} /></label><label className="publication-cover-file"><Camera size={16} />Tomar foto<input type="file" accept="image/*" capture="environment" onChange={choose} /></label>{file&&<button type="button" onClick={()=>onChange(null)}><X size={14} />Quitar selección</button>}<small>JPEG, PNG, GIF o WebP · hasta 5 MB. Solo afecta a esta publicación.</small></div>
    </div>}
    {error&&<p className="comment-error" role="alert">{error}</p>}
  </fieldset>
}
