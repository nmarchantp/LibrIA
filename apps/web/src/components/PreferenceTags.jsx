export default function PreferenceTags({ values, empty }) {
  return values.length ? <ul className="reader-taste-tags">{values.map(value => <li key={value.id}>{value.name}</li>)}</ul> : <p className="reader-module-empty">{empty}</p>
}
