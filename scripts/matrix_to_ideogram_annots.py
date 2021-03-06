#!/usr/bin/env python

"""Converts clustered gene expression matrices to Ideogram.js annotations
"""

__author__ = 'Eric Weitz, Jonathan Bistline, Timothy Tickle'
__copyright__ = 'Copyright 2018'
__credits__ = ['Eric Weitz']
__license__ = 'BSD-3'
__maintainer__ = 'Eric Weitz'
__email__ = 'eweitz@bbroadinstitute.org'
__status__ = 'Development'

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import json
from statistics import mean


class MatrixToIdeogramAnnots:

    def __init__(self, infercnv_output, infercnv_delimiter, gen_pos_file,
                 clusters_meta, output_file):
        """Class and parameter docs in module summary and argument parser"""

        self.infercnv_output = infercnv_output
        self.infercnv_delimiter = infercnv_delimiter
        self.clusters = self.get_clusters(clusters_meta)
        self.output_file = output_file
        self.genomic_position_file_path = gen_pos_file

        self.genes = self.get_genes()

        self.write_ideogram_annots()

    def write_ideogram_annots(self):
        """Write Ideogram.js annotations JSON data to specified output file"""

        ideogram_annots = self.get_ideogram_annots()

        ideogram_annots_json = json.dumps(ideogram_annots)

        with open(self.output_file, 'w') as f:
            f.write(ideogram_annots_json)

        print('Wrote Ideogram.js annotations to ' + self.output_file)

    def get_ideogram_annots(self):
        """Get Ideogram.js annotations from inferCNV and cluster data

        Format and other details of Ideogram.js annotations:
        https://github.com/eweitz/ideogram/wiki/Annotations
        """

        genes = self.genes

        expression_means = self.compute_gene_expression_means()

        keys = ['name', 'start', 'length']
        keys += ['all'] + list(self.clusters.keys())  # cluster names

        annots_by_chr = {}

        for i, expression_mean in enumerate(expression_means[1:]):
            gene_id = expression_mean[0]
            gene = genes[gene_id]

            chr = gene['chr']
            start = int(gene['start'])
            stop = int(gene['stop'])
            length = stop - start

            if chr not in annots_by_chr:
                annots_by_chr[chr] = []

            annot = [gene_id, start, length]

            if i % 1000 == 0 and i != 0:
                print('Constructed ' + str(i) + ' of ' + str(len(expression_means) - 1) + ' annots')

            annot += expression_mean[1:]

            annots_by_chr[chr].append(annot)

        annots_list = []

        for chr in annots_by_chr:
            annots = annots_by_chr[chr]
            annots_list.append({'chr': chr, 'annots': annots})

        ideogram_annots = {'keys': keys, 'annots': annots_list}

        return ideogram_annots

    def get_genes(self):
        """Convert inferCNV genomic position file into useful 'genes' dict"""

        genes = {}

        with open(self.genomic_position_file_path) as f:
            lines = f.readlines()

        for line in lines:
            columns = line.strip().split()
            id, chr, start, stop = columns
            genes[id] = {
                'id': id,
                'chr': chr,
                'start': start,
                'stop': stop
            }

        return genes

    def get_expression_matrix_dict(self):
        """Parse inferCNV output, return dict of cell expressions by gene"""
        print(self.get_expression_matrix_dict.__doc__)

        em_dict = {}

        with open(self.infercnv_output) as f:
            lines = f.readlines()

        cells_dict = {}

        cells_list = lines[0].strip().split(self.infercnv_delimiter)

        for i, cell in enumerate(cells_list):
            cell = cell.strip('"').split('PREVIZ.')[1].replace('.', '-')  # "PREVIZ.AAACATACAAGGGC.1" -> AAACATACAAGGGC-1
            cells_dict[cell] = i

        em_dict['cells'] = cells_dict
        genes = {}

        for line in lines[1:]:
            columns = line.strip().split(self.infercnv_delimiter)
            gene = columns[0].strip('"')
            expression_by_cell = list(map(float, columns[1:]))

            genes[gene] = expression_by_cell

        em_dict['genes'] = genes

        return em_dict

    def get_clusters(self, clusters_meta):
        """Assign cells from expression matrix to the appropriate cluster"""

        clusters = clusters_meta

        for name in clusters:

            cells = []

            clusters[name]['cells'] = []
            cluster_path = clusters[name]['path']

            with open(cluster_path) as f:
                lines = f.readlines()

            for line in lines[3:]:
                cell = line.split()[0]
                cells.append(cell)

            clusters[name]['cells'] = cells

        return clusters


    def compute_gene_expression_means(self):
        """Compute mean expression for each gene across all and each cluster"""

        scores_lists = []

        cluster_names = list(self.clusters.keys())

        keys = ['name', 'all'] + cluster_names
        scores_lists.append(keys)

        matrix = self.get_expression_matrix_dict()

        cells = matrix['cells']
        clusters = self.clusters

        gene_expression_lists = matrix['genes']

        # For each gene, get its mean expression across all cells,
        # then iterate through each cluster (a.k.a. ordination),
        # and get the mean expression across all cells in that cluster
        for i, gene in enumerate(gene_expression_lists):

            gene_exp_list = gene_expression_lists[gene]
            mean_expression_all = round(mean(gene_exp_list), 3)

            scores_list = [gene, mean_expression_all]

            for name in clusters:
                cluster = clusters[name]
                cluster_expressions = []
                for cluster_cell in cluster['cells']:
                    # if cluster_cell in cells:
                    index_of_cell_in_matrix = cells[cluster_cell] - 1
                    # else:
                    #     if i == 0:
                    #         print(cluster_cell + ' from ' + name + ' not found in expression matrix')
                    #     continue
                    gene_exp_in_cell = gene_exp_list[index_of_cell_in_matrix]
                    cluster_expressions.append(gene_exp_in_cell)

                mean_cluster_expression = round(mean(cluster_expressions), 3)
                scores_list.append(mean_cluster_expression)

            if i % 1000 == 0 and i != 0:
                print('Processed ' + str(i) + ' of ' + str(len(gene_expression_lists)))

            scores_lists.append(scores_list)

        return scores_lists


def get_clusters_meta(names, paths):
    """Organize cluster args provided via CLI into a more convenient dict"""

    if len(names) != len(paths):
        raise ValueError('Number of cluster names must equal length of cluster paths')

    clusters_meta = {}

    for i, name in enumerate(names):
        clusters_meta[name] = {'path': paths[i]}

    return clusters_meta


if __name__ == '__main__':

    # Parse command-line arguments
    ap = ArgumentParser(description=__doc__,  # Use text from file summary up top
                        formatter_class=RawDescriptionHelpFormatter)
    ap.add_argument('--infercnv_output',
                    help='Path to pre_vis_transform.txt output from inferCNV')
    ap.add_argument('--infercnv_delimiter',
                    help='Delimiter in pre_vis_transform.txt output from inferCNV.  Default: \\t',
                    default='\t')
    ap.add_argument('--gen_pos_file',
                    help='Path to gen_pos.txt genomic positions file from inferCNV ')
    ap.add_argument('--cluster_names',
                    help='List of cluster names',
                    nargs='+')  # List must have one or more items
    ap.add_argument('--cluster_paths',
                    help='List of cluster paths or URLs',
                    nargs='+')
    ap.add_argument('--output_file',
                    help='Path for write output')

    args = ap.parse_args()

    infercnv_output = args.infercnv_output
    infercnv_delimiter = args.infercnv_delimiter
    gen_pos_file = args.gen_pos_file
    cluster_names = args.cluster_names
    cluster_paths = args.cluster_paths
    output_file = args.output_file

    clusters_meta = get_clusters_meta(cluster_names, cluster_paths)

    MatrixToIdeogramAnnots(infercnv_output, infercnv_delimiter, gen_pos_file, clusters_meta, output_file)
