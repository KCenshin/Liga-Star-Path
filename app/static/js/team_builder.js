// Constructor de equipos: 6 ranuras con autocompletado contra /api/pokemon/search (caché local)
// y detalles bajo demanda (/api/pokemon/<id>) sólo al seleccionar un Pokémon.
(function () {
  const builder = document.getElementById('builder');
  const tpl = document.getElementById('slot-tpl');
  const unknown = window.UNKNOWN_SPRITE;

  const debounce = (fn, ms) => {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  };
  const pretty = s => s.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  function typeChip(t) {
    const s = document.createElement('span');
    s.className = `type type-${t}`;
    s.textContent = t;
    return s;
  }

  function buildSlot(i, initial) {
    const el = tpl.content.firstElementChild.cloneNode(true);
    const n = i + 1;
    const q = sel => el.querySelector(sel);
    q('.slot-num').textContent = `Ranura ${n}`;
    q('.f-id').name = `slot${n}_id`;
    q('.f-nickname').name = `slot${n}_nickname`;
    q('.f-item').name = `slot${n}_item`;
    q('.f-ability').name = `slot${n}_ability`;
    q('.f-tera').name = `slot${n}_tera`;

    const input = q('.ac-input');
    const list = q('.ac-list');
    const abilitySel = q('.f-ability');
    let active = -1;

    function setAbilities(abilities, selected) {
      abilitySel.innerHTML = '<option value="">—</option>';
      abilities.forEach(a => {
        const o = document.createElement('option');
        o.value = a.name;
        o.textContent = pretty(a.name) + (a.hidden ? ' (oculta)' : '');
        if (a.name === selected) o.selected = true;
        abilitySel.appendChild(o);
      });
      if (selected && !abilities.some(a => a.name === selected)) {
        const o = new Option(pretty(selected), selected, true, true);
        abilitySel.appendChild(o);
      }
    }

    async function loadDetails(id, selectedAbility) {
      abilitySel.disabled = true;
      try {
        const r = await fetch(`/api/pokemon/${id}`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.error);
        setAbilities(d.abilities, selectedAbility);
      } catch (e) {
        setAbilities([], selectedAbility);
        abilitySel.title = 'No se pudieron cargar las habilidades: ' + e.message;
      } finally {
        abilitySel.disabled = false;
      }
    }

    function setPokemon(p, data = {}) {
      q('.f-id').value = p ? p.id : '';
      q('.sprite').src = p && p.sprite ? p.sprite : unknown;
      q('.sprite').alt = p ? p.name : '';
      const name = q('.slot-poke-name');
      name.textContent = p ? (p.alt_form ? p.display : `#${p.id} ${p.display}`) : 'Vacío';
      name.classList.toggle('muted', !p);
      const types = q('.types');
      types.innerHTML = '';
      (p ? p.types : []).forEach(t => types.appendChild(typeChip(t)));
      el.classList.toggle('filled', !!p);
      input.value = '';
      q('.f-nickname').value = data.nickname || '';
      q('.f-item').value = data.item || '';
      q('.f-tera').value = data.tera || '';
      if (p) loadDetails(p.id, data.ability || ''); else setAbilities([], '');
    }

    function close() { list.hidden = true; list.innerHTML = ''; active = -1; }

    const search = debounce(async () => {
      const term = input.value.trim();
      if (term.length < 2 && !/^\d+$/.test(term)) return close();
      const r = await fetch(`/api/pokemon/search?q=${encodeURIComponent(term)}`);
      const results = await r.json();
      list.innerHTML = '';
      if (!results.length) {
        const li = document.createElement('li');
        li.className = 'ac-empty';
        li.textContent = 'Sin resultados';
        list.appendChild(li);
      }
      results.forEach(p => {
        const li = document.createElement('li');
        const img = document.createElement('img');
        img.src = p.sprite || unknown; img.alt = '';
        const label = document.createElement('span');
        label.textContent = p.alt_form ? p.display : `#${p.id} ${p.display}`;
        li.append(img, label);
        if (p.alt_form) {
          const tag = document.createElement('span');
          tag.className = 'form-tag';
          tag.textContent = 'Forma';
          li.appendChild(tag);
        }
        p.types.forEach(t => li.appendChild(typeChip(t)));
        li.addEventListener('mousedown', ev => { ev.preventDefault(); setPokemon(p); close(); });
        list.appendChild(li);
      });
      list.hidden = false;
    }, 180);

    input.addEventListener('input', search);
    input.addEventListener('blur', () => setTimeout(close, 100));
    input.addEventListener('keydown', ev => {
      const items = [...list.querySelectorAll('li:not(.ac-empty)')];
      if (!items.length) return;
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        active = (active + (ev.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items.forEach((li, j) => li.classList.toggle('active', j === active));
      } else if (ev.key === 'Enter') {
        ev.preventDefault();
        items[Math.max(active, 0)].dispatchEvent(new MouseEvent('mousedown'));
      } else if (ev.key === 'Escape') close();
    });
    q('.slot-clear').addEventListener('click', () => setPokemon(null));

    setPokemon(initial && initial.pokemon, initial || {});
    return el;
  }

  (window.TEAM_SLOTS || []).forEach((s, i) => builder.appendChild(buildSlot(i, s)));
})();
