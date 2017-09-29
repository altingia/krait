#!/usr/bin/env python
import pyfaidx

def initial_matrix(size):
	matrix = []
	for i in range(size+1):
		matrix.append([])
		for j in range(size+1):
			if i == 0:
				matrix[i].append(j)
			elif j == 0:
				matrix[i].append(i)
			else:
				matrix[i].append('#')

	return matrix

def print_matrix(matrix):
	for i in range(len(matrix)):
		print "\t".join(map(str,matrix[i]))
		
def build_left_matrix(seq, motif, matrix, start, size, max_error):
	i = 0
	j = 0
	n = 1
	x = 1
	prev_min = 0
	next_min = 0
	top_min = 0
	left_min = 0
	ref1 = None
	ref2 = None
	mlen = len(motif)
	consecutive_error = 0
	cumulative_error = 0

	while n<=size:
		ref1 = seq[start-n]
		ref2 = motif[(mlen-n%mlen)%mlen]
		#min edit
		top_min = matrix[0][n]
		left_min = matrix[n][0]

		#fill column
		for x in range(1, n):
			if ref1 == motif[(mlen-x%mlen)%mlen]:
				matrix[x][n] = matrix[x-1][n-1]
			else:
				matrix[x][n] = min(matrix[x-1][n-1], matrix[x-1][n], matrix[x][n-1]) + 1

			if matrix[x][n] < top_min:
				top_min = matrix[x][n]

			if ref2 == seq[start-x]:
				matrix[n][x] = matrix[n-1][x-1]
			else:
				matrix[n][x] = min(matrix[n-1][x-1], matrix[n-1][x], matrix[n][x-1]) + 1

			if matrix[n][x] < left_min:
				left_min = matrix[n][x]

		if ref1 == ref2:
			matrix[n][n] = matrix[n-1][n-1]
		else:
			matrix[n][n] = min(matrix[n-1][n-1], matrix[n-1][n], matrix[n][n-1]) + 1

		next_min = min(matrix[n][n], top_min, left_min)

		if next_min > prev_min:
			consecutive_error += 1
			cumulative_error += 1
		else:
			consecutive_error = 0

		prev_min = next_min

		if consecutive_error > max_error:
			break

		if n > mlen and cumulative_error*1.0/n > 0.5:
			break
		
		n += 1

	if n > size:
		n -= 1
	

	n -= consecutive_error
	
	#top min
	for top_pos in range(n-1, 0, -1):
		if matrix[top_pos][n] < matrix[top_pos-1][n]:
			top_min = matrix[top_pos][n]
			break

	#left min
	for left_pos in range(n-1, 0, -1):
		if matrix[n][left_pos] < matrix[n][left_pos-1]:
			left_min = matrix[n][left_pos]
			break

	top_min = matrix[n][n]
	left_min = matrix[n][n]
	for x in range(n-1, 0, -1):
		if matrix[x][n] > top_min:
			break
		top_min = matrix[x][n]

	for x in range(n-1, 0, -1):
		if matrix[n][x] > left_min:
			break
		
		left_min = matrix[n][x]


	next_min = min(top_min, left_min, matrix[n][n])

	if next_min == matrix[n][n]:
		i = n
		j = n
	elif next_min == top_min:
		i = top_pos
		j = n
	else:
		i = n
		j = left_pos

	#print_matrix(matrix)
	
	return (i, j)

def build_right_matrix(seq, motif, matrix, start, size, max_error):
	i = 1 #row number
	j = 1 #column number
	x = 1 #diagonal i
	y = 1 #diagonal j
	ref1 = None
	ref2 = None
	mlen = len(motif)
	consecutive_error = 0
	last_x = 0
	last_y = 0

	while y<=size:
		ref1 = seq[start+y]
		ref2 = motif[(x-1)%mlen]
		#fill column column number fixed
		if i != y:
			for i in range(1, x):
				if ref1 == motif[(i-1)%mlen]:
					matrix[i][y] = matrix[i-1][y-1]
				else:
					matrix[i][y] = min(matrix[i-1][y-1], matrix[i-1][y], matrix[i][y-1]) + 1

		#fill row, row number fixed
		if j != x:
			for j in range(1, y):
				if ref2 == seq[start+j]:
					matrix[x][j] = matrix[x-1][j-1];
				else:
					matrix[x][j] = min(matrix[x-1][j-1], matrix[x-1][j], matrix[x][j-1]) + 1

		i = y
		j = x

		if ref1 == ref2:
			matrix[x][y] = matrix[x-1][y-1]
			consecutive_error = 0
		else:
			if consecutive_error == 0:
				last_x = x-1
				last_y = y-1
			consecutive_error += 1
			matrix[x][y] = min(matrix[x-1][y-1], matrix[x-1][y], matrix[x][y-1]) + 1

			smaller = min(matrix[x][y], matrix[x-1][y], matrix[x][y-1])

			if smaller != matrix[x][y]:
				if matrix[x-1][y] != matrix[x][y-1]:
					if smaller == matrix[x][y-1]:
						y -= 1
					else:
						x -= 1
			
		if consecutive_error > max_error:
			return (last_x, last_y)
		
		x += 1
		y += 1

	#print_matrix(matrix)

	if consecutive_error:
		return (last_x, last_y)
	else:
		return (x-1, y-1)

def backtrace_matrix(matrix, diagonal):
	i, j = diagonal

	substitution = 0
	insertion = 0
	deletion = 0
	match = 0
	x = i
	y = j
	while i>0 and j>0:
		cost = min(matrix[i-1][j-1], matrix[i-1][j], matrix[i][j-1])
		if cost == matrix[i-1][j-1]:
			if cost == matrix[i][j]:
				match += 1
			else:
				substitution += 1

			i -= 1
			j -= 1

		elif cost == matrix[i-1][j]:
			deletion += 1
			i -= 1

		else:
			insertion += 1
			j -= 1

	if i>0:
		deletion += 1
	elif j>0:
		insertion += 1

	return (x, y, match, substitution, insertion, deletion)


def search_issr(seq, seed_repeats, seed_minlen, max_errors, mis_penalty, gap_penalty, required_score, size):
	res = []
	matrix = initial_matrix(size)
	seqlen = len(seq)
	i = 0
	while i < seqlen:
		if seq[i] == 'N':
			i += 1
			continue

		j = 1
		while j <= 6:
			seed_start = i
			seed_length = j
			while seed_start+seed_length < seqlen and seq[i] == seq[i+j] and seq[i] != 'N':
				i += 1
				seed_length += 1

			seed_repeat = seed_length/j

			if seed_repeat >= seed_repeats and seed_length >= seed_minlen:
				motif = seq[seed_start:seed_start+j]

				seed_end = seed_start + seed_length - seed_length%j - 1
				matches = seed_length - seed_length%j
				insertion = 0
				deletion = 0
				substitution = 0
				
				#extend left
				'''
				extend_start = seed_start
				extend_len = extend_start
				if extend_len > size:
					extend_len = size
				extend_end = build_left_matrix(seq, motif, matrix, extend_start, extend_len, max_errors)
				extend_ok = backtrace_matrix(matrix, extend_end)
				start = extend_start - extend_ok[1] + 1
				matches += extend_ok[2]
				substitution += extend_ok[3]
				insertion += extend_ok[4]
				deletion += extend_ok[5]
				'''
				start = seed_start + 1
				#extend right
				extend_start = seed_end
				extend_len = seqlen - extend_start - 1
				if extend_len > size:
					extend_len = size
				extend_end = build_right_matrix(seq, motif, matrix, extend_start, extend_len, max_errors)
				extend_ok = backtrace_matrix(matrix, extend_end)
				end = extend_start + extend_ok[1] + 1
				length = end - start + 1
				matches += extend_ok[2]
				substitution += extend_ok[3]
				insertion += extend_ok[4]
				deletion += extend_ok[5]

				score = matches - substitution*mis_penalty - (insertion+deletion)*gap_penalty
				
				if score >= required_score:
					res = (motif, j, start, end, length, matches, substitution, insertion, deletion, score)
					print "%s\t%s" % (",".join(map(str, res)), seq[start-1:end])
					i = end
					j = 0
				else:
					i = seed_start
			else:
				i = seed_start
			j += 1
		i += 1

	#return res

if __name__ == '__main__':
	fasta = pyfaidx.Fasta('test.fa')
	seq = str(fasta['NC_000913.3'])
	#seq = "AAGAAGAAGATGAAGAGAAGTTTTTTT"
	#seq = "AAAAAAAAATCATTT"
	#seq = "TCATCATCAAAATCGCCAT"
	search_issr(seq, 3, 8, 3, 1, 2, 10, 500)
	#seq = "GTTGTTGTTGATTG"
	#search_issr(seq, 3, 8, 3, 2, 5, 3, 20)

		
	