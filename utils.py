#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
import csv
import gzip

from libs import *
from config import *

class Data(dict):
	def __getattr__(self, name):
		try:
			return self[name]
		except KeyError:
			raise AttributeError(name)

	def __setattr__(self, name, val):
		self[name] = val

def sortfilter(it, index=0, count=20):
	it = sorted(it, key=lambda x:x[index], reverse=True)
	return it[:20]

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
env.filters['sortfilter'] = sortfilter
def template_render(template_name, **kwargs):
	template = env.get_template(template_name)
	return template.render(**kwargs)

def write_to_tab(tabfile, headers, cursor):
	'''
	write data to tabular file with \t separator
	@tabfile str, the save file path
	@headers tuple, the columns of the table
	@cursor, the database cursor
	'''
	with open(tabfile, 'w') as tab:
		tab.write("%s\n" % "\t".join(headers))
		for row in cursor:
			tab.write("%s\n" % "\t".join(map(str, row)))

def write_to_csv(csvfile, headers, cursor):
	with open(csvfile, 'wb') as cf:
		writer = csv.writer(cf)
		writer.writerow(headers)
		for row in cursor:
			writer.writerow(row)

def write_to_gff(gff_file, feature, cursor):
	with open(gff_file, 'w') as gff:
		gff.write("##gff-version 3\n")
		gff.write("##generated by Krait %s\n" % VERSION)
		for row in cursor:
			cols = [row.sequence, 'Krait', feature, row.start, row.end, '.', '+', '.', []]
			cols[-1].append("ID=%s%s" % (feature, row.id))
			cols[-1].append("Motif=%s" % row.motif)
			for k in row.getKeys():
				if k not in ['id', 'sequence', 'start', 'end', 'motif']:
					cols[-1].append("%s=%s" % (k.capitalize(), row.value(k)))
			cols[-1] = ";".join(cols[-1])
			gff.write("\t".join(map(str, cols))+'\n')

def write_to_gtf(gtf_file, feature, cursor):
	with open(gtf_file, 'w') as gtf:
		gtf.write("#!gtf-version 2\n")
		gtf.write("#!generated by Krait %s\n" % VERSION)
		for row in cursor:
			cols = [row.sequence, 'Krait', feature, row.start, row.end, '.', '+', '.', []]
			cols[-1].append('gene_id "%s%s"' % (feature, row.id))
			cols[-1].append('transcript_id "%s%s"' % (feature, row.id))
			cols[-1].append('motif "%s"' % row.motif)
			for k in row.getKeys():
				if k not in ['id', 'sequence', 'start', 'end', 'motif']:
					cols[-1].append('%s "%s"' % (k, row.value(k)))
			cols[-1] = "; ".join(cols[-1])
			gtf.write("\t".join(map(str, cols))+'\n')

def format_sql_where(conditions):
	symbols = ['>=', '<=', '>', '<', '=', ' in ']
	conditions = conditions.split()
	for idx, cond in enumerate(conditions):
		if cond == 'in':
			items = conditions[idx+1].strip('()').split(',')
			if not items[0].isdigit():
				conditions[idx+1] = "(%s)" % ",".join(map(lambda x: "'%s'" % x, items))
			continue

		if cond in symbols:
			if not conditions[idx+1].isdigit():
				conditions[idx+1] = "'%s'" % conditions[idx+1]
			continue

		for symbol in symbols:
			if symbol in cond:
				res = cond.split(symbol)
				if not res[1].isdigit():
					res[1] = "'%s'" % res[1]
					conditions[idx] = "%s%s%s" % (res[0], symbol, res[1])

	return " ".join(conditions)

def format_fasta_sequence(sequence, length):
	seqs = []
	for idx, base in enumerate(sequence):
		seqs.append(base)
		if (idx+1) % length == 0:
			seqs.append('\n')
	seqs.append('\n')
	return "".join(seqs)

def check_gene_annot_format(annot_file):
	if annot_file.endswith('.gz'):
		fh = gzip.open(annot_file)
	else:
		fh = open(annot_file)

	for line in fh:
		if line[0] == '#': continue
		cols = line.strip().split('\t')
		if cols[2].upper() != 'EXON': continue
		if cols[-1].count('=') > 2:
			return 'GFF'
		elif 'transcript_id' in cols[-1]:
			return 'GTF'
		else:
			raise Exception('The annotation file is not GTF or GFF format')


def gff_gtf_parser(annot_file, _format='GFF'):
	"""
	parse GFF, GTF, comparessed gz annotation file
	"""
	if annot_file.endswith('.gz'):
		fh = gzip.open(annot_file)
	else:
		fh = open(annot_file)

	for line in fh:
		if line[0] == '#': continue
		cols = line.strip().split('\t')
		record = Data()
		record.seqid = cols[0]
		record.feature = cols[2].upper()
		record.start = int(cols[3])
		record.end = int(cols[4])
		record.attrs = {}
		
		for item in cols[-1].split(';'):
			if not item: continue
			if _format == 'GFF':
				name, value = item.split('=')
			else:
				name, value = item.strip().strip('"').split('"')
			record.attrs[name.strip().upper()] = value
		
		yield record

	fh.close()

def get_gtf_coordinate(gtf_file):
	father = None
	exons = []
	for r in gff_gtf_parser(gtf_file, 'GTF'):
		if r.feature == 'GENE':
			yield ('GENE', r.attrs['GENE_ID'], r.attrs['GENE_NAME'])
		elif r.feature == 'CDS':
			yield ('CDS', r.seqid, r.start, r.end, r.attrs['GENE_ID'])
		elif r.feature == 'FIVE_PRIME_UTR':
			yield ('5UTR', r.seqid, r.start, r.end, r.attrs['GENE_ID'])
		elif r.feature == 'THREE_PRIME_UTR':
			yield ('3UTR', r.seqid, r.start, r.end, r.attrs['GENE_ID'])
		elif r.feature == 'EXON':
			mother = r.attrs['TRANSCRIPT_ID']

			if father == mother:
				exons.append(('EXON', r.seqid, r.start, r.end, r.attrs['GENE_ID']))
			else:
				if exons:
					exons = sorted(exons, key=lambda x: x[2])
					for idx, exon in enumerate(exons):
						start, end = exon[2], exon[3]
						yield exon

						if idx < len(exons)-1:
							start = end+1
							end = exons[idx+1][2]-1
							yield ('INTRON', exons[0][1], start, end, exons[0][4])
				
				exons = [('EXON', r.seqid, r.start, r.end, r.attrs['GENE_ID'])]
				father = mother

	exons = sorted(exons, key=lambda x: x[2])
	for idx, exon in enumerate(exons):
		start, end = exon[2], exon[3]
		yield exon

		if idx < len(exons)-1:
			start = end+1
			end = exons[idx+1][2]-1
			yield ('INTRON', exons[0][1], start, end, exons[0][4])

def get_gff_coordinate(gff_file):
	father = None
	exons = []
	relations = {}
	for r in gff_gtf_parser(gff_file, 'GFF'):
		if 'ID' in r.attrs and 'PARENT' in r.attrs:
			relations[r.attrs['ID']] = r.attrs['PARENT']

		if r.feature == 'GENE':
			yield ('GENE', r.attrs['ID'], r.attrs['NAME'])
		elif r.feature == 'CDS':
			yield ('CDS', r.seqid, r.start, r.end, relations[r.attrs['PARENT']])
		elif r.feature == 'FIVE_PRIME_UTR':
			yield ('5UTR', r.seqid, r.start, r.end, relations[r.attrs['PARENT']])
		elif r.feature == 'THREE_PRIME_UTR':
			yield ('3UTR', r.seqid, r.start, r.end, relations[r.attrs['PARENT']])
		elif r.feature == 'EXON':
			mother = r.attrs['PARENT']

			if father == mother:
				exons.append(('EXON', r.seqid, r.start, r.end, relations[r.attrs['PARENT']]))
			else:
				if exons:
					exons = sorted(exons, key=lambda x: x[2])
					for idx, exon in enumerate(exons):
						start, end = exon[2], exon[3]
						yield exon

						if idx < len(exons)-1:
							start = end+1
							end = exons[idx+1][2]-1
							yield ('INTRON', exons[0][1], start, end, exons[0][4])
				
				exons = [('EXON', r.seqid, r.start, r.end, relations[r.attrs['PARENT']])]
				father = mother

	exons = sorted(exons, key=lambda x: x[2])
	for idx, exon in enumerate(exons):
		start, end = exon[2], exon[3]
		yield exon

		if idx < len(exons)-1:
			start = end+1
			end = exons[idx+1][2]-1
			yield ('INTRON', exons[0][1], start, end, exons[0][4])


def get_ssr_sequence(seq_file, seq_name, start, stop, flank):
	'''
	Get the SSR sequence and flanking sequences
	@para seq_file, the file path of the fasta sequence
	@para seq_name, the name of the fasta sequence
	@para start, the start position of SSR
	@para stop, the stop position of SSR
	@para flank, the length of the flanking sequence
	@return ssr sequence with flanking sequences
	'''
	fastas = fasta.Fasta(seq_file, sequence_always_upper=True)
	
	#get ssr sequence
	ssr = fastas[seq_name][start-1:stop].seq
	
	#get left flanking sequence
	left_flank_start = start - flank - 1
	if left_flank_start < 0:
		left_flank_start = 0
	left_flank = fastas[seq_name][left_flank_start:start]
	
	seq_len = len(fastas[seq_name])
	
	#get right flanking sequence
	right_flank_stop = stop + flank
	if right_flank_stop > seq_len:
		right_flank_stop = seq_len
	right_flank = fastas[seq_name][stop:right_flank_stop]

	highlighter = SequenceHighlighter()
	meta = '%s:%s-%s %s' % (seq_name, left_flank_start+1, start, len(left_flank))
	highlighter.format_flank(left_flank, meta)
	highlighter.format_ssr(ssr)
	highlighter.format_flank(right_flank)
	return highlighter.render()

def human_size(size):
	if size < 1000:
		return '%s bp' % round(size, 2)

	size = size/1000
	if size < 1000:
		return '%s kb' % round(size, 2)

	size = size/1000
	return '%s Mb' % round(size, 2)

