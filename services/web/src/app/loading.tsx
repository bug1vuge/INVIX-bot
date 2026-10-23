export default function Loading() {
  return (
    <main className="page" aria-busy="true">
      <h1 className="title">Каталог</h1>
      <ul className="grid">
        {Array.from({ length: 6 }, (_, index) => (
          <li key={index} className="card card--skeleton" aria-hidden="true">
            <div className="card__media" />
            <p className="card__name">&nbsp;</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
