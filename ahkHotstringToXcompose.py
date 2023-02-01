s = """

	::==>::
		Send % "⟹ "
    return
	::=>::
		Send % "⇒ "
	return
	::<==::
		Send % "⟸ "
	return
	::<=>::
		Send % "⇔ "
	return

	::-->::
		Send % "⟶ "
	return
	::->::
		Send % "↦"
	return
	::<- ::
		Send % "↤"
	return
	::<--::
		Send % "⟵ "
	return
	::i->::
		Send % "↪ "
	return
	::->>::
		Send % "↠ "
	return
	::<=::
		Send % "≤ "
	return
	::>=::
		Send % "≥ "
	return
	::!=:: 
		Send % "≠ "
	return
	::=d::
		Send % "≝ "
	return
	::=^::
		Send % "≙ "
	return

	::>m::
		Send % "⊇ "
	return
	::<m::
		Send % "⊆ "
	return

	::<e::
		Send % "∈ "
	return
	::>e::
		Send % "∋ "
	return
	::<i::
		Send % "∊ "
	return
	::>i::
		Send % "∍ "
	return

	::<<::
		Send % "≪ "
	return

	::+-::
		Send ±
	return
	::-+::
		Send ∓
	return

	:::=:: 
		Send ≔
	return

	::=: ::
		Send % "≕ "
	return

	::rrr::
		Send ℝ
	return
"""
c = ''
o=''
r=''
d = {
    '>': 'greater',
    '<': 'less',
    '=': 'equal',
    ':': 'colon',
    '-': 'minus',
    '+': 'plus',
    ' ': 'space',
    '^':  'asciicircum'
}
def encode(t):
    res = '<Multi_key>'
    for k in t:
        res += '<'+ d.get(k,k)+'>'
    return res

for l in s.splitlines():
    l = l.strip()
    if l.startswith('::') and l.endswith('::'):
        c = encode(l[2:-2])
    elif l.startswith('Send'):
        o = l[4:].strip(' %').strip('"')
    elif l == 'return':
        r += f'{c}: "{o}"\n'

print(r)