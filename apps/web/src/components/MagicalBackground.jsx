import './MagicalBackground.css'

// Mounted once by Layout; route changes do not restart these CSS animations.
export default function MagicalBackground({ motionEnabled = true }) {
  return <div className="profile-starfield" data-motion={motionEnabled ? 'enabled' : 'disabled'} aria-hidden="true">
    <span className="profile-starfield-layer profile-starfield-layer--fine" />
    <span className="profile-starfield-layer profile-starfield-layer--medium" />
    <span className="profile-starfield-layer profile-starfield-layer--large" />
  </div>
}
