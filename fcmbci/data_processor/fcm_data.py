import sys, os
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

import pandas as pd
import itertools
import numpy as np
import skfuzzy as fuzz
import skfuzzy
import matplotlib.pyplot as plt
import matplotlib
import re
import networkx as nx
import functools
from data_processor.process_functions import *

class FcmDataProcessor:

    """
    A class of methods to derive causal weights for FCMs based on linguistic terms.
    The FcmBci object is initialized with a universe of discourse with a range [0,1]. 
    """
    
    def __init__(self, data = None):
        
        if data != None:
            self.data = data
        else:
            self.data = pd.DataFrame()
        self.universe = np.arange(-1, 1.001, 0.001)

    def read_xlsx(self, file_name, dtype):
        
        """ Reads an excel spreadsheet into the constructor.
        Note that the first column in the file is set to be the index.
        
        Parameters
        ----------
        file_name : str, 
                    ExcelFile, xlrd.Book, path object or file-like object (read more in pd.read_excel)
        
        dtype: str,
                Data type. Available options --> 'Matrix', 'List'.
        """
        
        if dtype.lower() not in ['matrix', 'list']:
            raise ValueError(f'Unrecognized data format "{dtype}"! Check the spelling or the data type!')
        
        if dtype.lower() == 'matrix':
            data = pd.read_excel(file_name, index_col = 0, sheet_name=None)
            consistency_check(data, 'Matrix') # if inconsistent then it will throw an error
            self.data = data
        else:
            data = pd.read_excel(file_name, sheet_name=None)
            check_column(data)
            consistency_check(data, 'List')
            self.data = data            
        
    #### Obtaining (numerical) causal weights based on expert (linguistic) inputs.
    
    def automf(self, universe, 
               linguistic_terms = ['-VH', '-H', '-M', '-L','-VL', 'VL','L', 'M', 'H', 'VH']):
        
        """ Automatically generates triangular membership functions based on the passed
        Lingustic Terms. This function was taken and modified from scikit-fuzzy.
        
        Parameters
        ----------
        universe : 1d array,
                    The universe of discourse.
                    
        linguistic_terms : lsit, 
                            default --> ['-VH', '-H', '-M', '-L', '-VL', 'VL', 'L', 'M', 'H', 'VH']
                            Note that the number of linguistic terms should be even. A narrow interval around 0 is added automatically.
        
        Return
        ---------
        y : dict,
            Generated membership functions. The key is the linguistic term and the value is a 1d array. 
        """
        
        number = len(linguistic_terms)
        limits = [universe.min(), universe.max()]
        universe_range = (limits[1] - limits[0])/2
        widths = [universe_range / (((number/2) - 1) / 2.)] * int(number)
        
        
        # Create the centers of the mfs for each side of the x axis and then merge them together.
        centers_pos = np.linspace(0.001, 1, number//2)
        centers_neg = np.linspace(-1, -0.001, number//2)
        centers = list(centers_neg)+list(centers_pos)
        
        abcs = [[c - w / 2, c, c + w / 2] for c, w in zip(centers, widths)]
        
        abcs[number//2] = [0.001, 0.001, centers_pos[1]] # + Very low 
        abcs[((number//2) -1)] = [centers_neg[-2], -0.001, -0.001] # - Very Low
        
        terms = dict()

        # Repopulate
        for term, abc in zip(linguistic_terms, abcs):
            terms[term] = skfuzzy.trimf(universe, abc)
        
        return terms

    
    def activate(self, activation_input, mf):
        
        """ Activate the specified membership function based on the passed parameters.
        
        Parameters
        ----------
        activation_input : dict,
                            Membership function to apply the implication operation, 
                            where the key is the linguistic term and the value is the frequency its occurence .
                            Example: parameters = {'H': 0.66, 'VH': 0.33}
        mf : dict,
             membership functions upon which the implication operator is applied. The key in the dict is the linguistic term, 
             and the value is a 1d array with the membership values.
        
        Return
        ---------
        y : dict,
            Activated membership functions, where the key is the linguistic term and 
            the value is a 1d array with the activated membership values. 
        """
        
        activated = {}
        for i in activation_input.keys():
            activated[i] = np.fmin(activation_input[i], mf[i])
        
        return activated
    
    def aggregate(self, activated):
        
        """ Aggregate the activated membership function usiing fmax operator. 
        
        Parameters
        ----------
        activated : dict,
                    A dictionary with the activated membership values to be aggregated.
        
        Return
        ---------
        y : 1d array,
            Aggregated membership function.
        """
        
        aggregated = functools.reduce(lambda x,y: np.fmax(x,y),
                             [activated[i] for i in activated.keys()])
        
        return aggregated
    
    def defuzzify(self, universe, aggregated, method = 'centroid'):
        
        """ Difuzzify the aggregated membership functions using centroid defuzzification method as a default.
        One can pass on another defuzzification method available in scikit-fuzzy library (e.g., bisector, mom, sig)
        Returns the defuzzified value.

        Parameters
        ----------
        universe : 1d array,
                    The universe of discourse.

        aggregated : 1d array,
                        Aggregated membership function to be defuzzified.
        method : str, 
                    Defuzzification method, default --> 'centroid'. 
                    For other defuzzification methods check scikit-fuzzy library (e.g., bisector, mom, sig)
        
        Return
        ---------
        y : int,
            Defuzzified value.
        """
        
        defuzzified_value = fuzz.defuzz(universe, aggregated, method)
        
        return defuzzified_value
        
    def gen_weights_mat(self, data = None,
                                linguistic_terms = ['-VH', '-H', '-M', '-L', '-VL', 'VL','L', 'M', 'H', 'VH'],
                                method = 'centroid'):
                
        """ This function applies fuzzy logic to obtain edge weights from FCM with qualitative inputs in a matrix format data (i.e., where the 
        causal relationships are expressed in linguistic terms).
        
        Parameters
        ----------
        data : dataframe,
                Expert input data. The row index and the column names should be the concepts and the row inputs should be the
                linguistic terms.
                default --> None; uses the data stored/read into the constructor.

        linguistic_terms : list,
                            A list of Linguistic Terms; default --> ['-VH', '-H', '-M', '-L', '-VL', 'VL','L', 'M', 'H', 'VH']
                            Note that the number of linguistic terms should be even. A narrow interval around 0 is added automatically.
        method : str,
                    Defuzzification method;  default --> 'centroid'. 
                    For other defuzzification methods check scikit-fuzzy library (e.g., bisector, mom, sig)
        """
        if data == None:
            data = self.data
            # Create a flat data with all of the experts' imputs.
            flat_data = pd.concat([data[i] for i in data], sort = False)
        else:
            consistency_check(data, 'Matrix')
            data = data      
            flat_data = pd.concat([data[i] for i in data], sort = False)
  

        # weight matrix for the final results.
        weight_matrix = pd.DataFrame(pd.DataFrame(columns=list(flat_data.index.unique()), index=list(flat_data.index.unique())))
        # For the freq_hist visualization
        self.expert_data = {}
        
        # A dict to store the aggregated results for the visualization purposes. 
        self.aggregated = {}
        
        # Create the membership functions for the linguistic terms.
        terms = self.automf(self.universe, linguistic_terms)
        self.terms = terms
        
        # for each pair of consequnt/antecedent calculate the edge value and store it in the weight matrix.
        for antecedent in flat_data:
            for consequent in flat_data:
                crostab = pd.crosstab(flat_data.loc[antecedent][consequent], flat_data.loc[antecedent][consequent].index)/len(data.keys())
                # check if the ant/cons pairs exist.
                if len(crostab) != 0:
                    activation_parameter = eval(str(crostab[antecedent].to_dict()).replace('"', '')) # create the parameter.
                    self.expert_data[(antecedent, consequent)] = activation_parameter # for the freq_term hist vis. 
                    
                    activated = self.activate(activation_parameter, self.terms) # activate the mf
                    aggregated = self.aggregate(activated) # aggregate the activated mfs
                    self.aggregated[f'{antecedent} {consequent}'] = aggregated # store the aggregated function for vis.
                    value = self.defuzzify(self.universe, aggregated, method) # defuzzify the values.
                    weight_matrix.loc[antecedent][consequent] = value # populate the df with the defuzzified  weights.
                    
        self.causal_weights = weight_matrix.fillna(0)
            
    
    def gen_weights_list(self, data = None,
                         linguistic_terms = ['-VH', '-H', '-M', '-L', '-VL', 'VL','L', 'M', 'H', 'VH'],
                         method = 'centroid'): 
        
        """ Apply fuzzy logic to obtain edge weights from FCM with qualitative inputs 
        (i.e., where the causal relationships are expressed in linguistic terms) in an edge list format data.
        
        Parameters
        ----------
        data : dataframe,
                Expert input data. The dataframe should have a From and To columns, followed by the linguistic terms. See an example
                in the documentation.
                default --> None; uses the data stored/read into the constructor.

        linguistic_terms : list,
                            A list of Linguistic Terms; default --> ['-VH', '-H', '-M', '-L', '-VL', 'VL','L', 'M', 'H', 'VH']
                            Note that the number of linguistic terms should be even. A narrow interval around 0 is added automatically.
        
        method : str,
                    Defuzzification method;  default --> 'centroid'. 
                    For other defuzzification methods check scikit-fuzzy library (e.g., bisector, mom, sig)
                    
        """        
        if data == None:
            data = self.data
            # Create a flat data with all of the experts' imputs.
            flat_data = pd.concat([data[i] for i in data], sort = False)
        else:
            consistency_check(data, 'List')
            data = data
            flat_data = pd.concat([data[i] for i in data], sort = False)

        
        # weight matrix for the final results.
        weight_matrix = pd.DataFrame(columns=[i for i in flat_data['From'].unique()], index=[i for i in flat_data['From'].unique()])
        self.expert_data = {}
        
        # 1) Calculate term frequencies, 2) add the signes to them. 3) set the NA's to 0.
        freq_data = pd.concat([data[i] for i in data],  ignore_index=True).groupby(['From', 'To']).count()/len(data.keys())
        signed = flat_data.groupby(['From', 'To']).mean() * freq_data # adds the sign of the terms
        final = signed.fillna(0) # sets the nan to 0
        
        # A dict to store the aggregated results for the visualization purposes. 
        self.aggregated = {}
        
        # Create the membership functions for the linguistic terms.
        terms = self.automf(self.universe, linguistic_terms)
        self.terms = terms

        for pair in final.index:
            activation_parameter = {}
            term_set = final.loc[pair[0], pair[1]].to_dict() # selects the term:freq for a pair of concepts.       
            
            # Attach the sign to the Linguistic Term.
            for term in term_set.keys():
                sign = str(np.sign(term_set[term])).strip('1\0.0\.\0') # extract the sign of the 
                value = float(str(term_set[term]).strip('-')) # striping the sign (the activation f only takes values in the fuzzy range.)
                key = sign + term
                activation_parameter[key] = value
            self.expert_data[pair] = activation_parameter
            # Activate, aggregate, defuzzify and attach the value to the weight_matrix. 
            if not all(x==0 for x in activation_parameter.values()): # Checks if at least one rull is activated.
                activated = self.activate(activation_parameter, terms)
                aggr = self.aggregate(activated)
                self.aggregated[f'{pair[0]} {pair[1]}'] = aggr
                value = self.defuzzify(self.universe, aggr, method)
                weight_matrix.loc[pair[0]][pair[1]] = value
        self.causal_weights = weight_matrix.fillna(0)
        
    def create_system(self, causal_weights = None):
        
        """ Creates a fuzzy system/network based on the generated causal weights.
        
        Parameters
        ----------
        causal_weights : dataframe,
                            dataframe with the causal wights where the columns and rows/index represent the concepts
                            and the rows represent the weights.
                            default --> None; Uses the casual weights stored in the constructor. 
        
        Return
        ----------
        y : networkx object,
        """

        if causal_weights == None:
            causal_weights = self.causal_weights
        else:
            causal_weights = causal_weights

        # Creates a netwrokx instance.
        G = nx.from_numpy_matrix(causal_weights.values, parallel_edges=True, 
                         create_using=nx.MultiDiGraph())
        
        # Creates truncated labels.
        labels = {idx: label_gen(val) for idx, val in enumerate(causal_weights.columns)}
        G = nx.relabel_nodes(G, labels)
        
        self.system = G