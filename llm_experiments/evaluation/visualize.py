import itertools
from adjustText import adjust_text
from utils.io import read_json_file
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_style("ticks")

NOISE_RATIOS = [round(i*1e-1, 1) for i in range(1, 9)]

def plot_f1_vs_noise(df):
    # Set the figure size
    plt.figure(figsize=(8, 5))
    

    
    # Create the line plot with markers using Seaborn
    ax = sns.lineplot(data=df, x='noise_ratio', y='f1', hue='model', 
                 linewidth=2.5, 
                 markers={"deepseek_v3_540b": "*"}, 
                 style="model", 
                 markersize=12,
                 markeredgecolor=None,
                 )
    for line in ax.lines:
        x_data = line.get_xdata()
        y_data = line.get_ydata()
        for x, y in zip(x_data, y_data):
            ax.annotate(
                text=f'{y:.1f}',
                xy=(x, y),
                xytext=(5, 0),  
                textcoords='offset points',
                fontsize=15,
                ha='left',     
                va='center'     
            )
    plt.xlim(0, 0.9)
    
    plt.grid(visible=True, linestyle='--', linewidth=1, color='black', alpha=0.3)
    plt.tick_params(axis='both', labelsize=15)
    plt.xlabel('Noise Ratio', fontsize=14)
    plt.ylabel('F1 Score', fontsize=14)
    plt.title('F1 Score vs Noise Ratio. Project: pmd-4.2.5. Perturbations: DiD', fontsize=15)
    plt.legend(title='Model',title_fontsize=10, fontsize=10)
    legend = ax.legend()
    ax.spines['bottom'].set_color('black')
    ax.spines['left'].set_color('black')
    ax.spines['left'].set_color('black')
    ax.spines['left'].set_color('black')
    legend.get_frame().set_linewidth(0.5)
    legend.get_frame().set_edgecolor('black')
    for text in legend.get_texts():
        text.set_color('black')
        text.set_fontsize(14)
    # for line in ax.lines:
    #     line.set_markersize(10)
    # for handle in legend.legend_handles:
    #     handle.set_markersize(5)
    # Save the plot as a PDF file
    plt.tight_layout()
    plt.savefig('f1_vs_noise_pmd-4.2.5_did_hybrid.pdf', format='pdf', bbox_inches='tight')
    plt.show()