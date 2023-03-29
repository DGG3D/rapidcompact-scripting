# rapidcompact-scripting
A scripting tool for the [RapidCompact REST API](https://api.rapidcompact.com/docs), based on Python and acting as a command line tool.

This script should serve as demonstration and starting point for your own API-based integration of RapidCompact.


## Basic Usage
To optimize one or multiple 3D models, to one or multiple target resolutions, simply perform the following steps:

1. Make sure you have [Python 3](https://www.python.org/) installed.

2. Edit "credentials.json" and enter your [API token](https://app.rapidcompact.com/app/api-tokens).  
  ![Illustration of Step 2](/tutorial/quick-intro/images/step2.JPG)

3. Edit the "variants.json" file to specify the desired resolution and output formats for your models (or keep it as-is for a first test run).  
  ![Illustration of Step 3](/tutorial/quick-intro/images/step3.JPG)

4. Execute a command line (for example, using Windows PowerShell) to invoke the `rpdc.py` script.
   Example:  
   `python3 rpdc.py input`     
   This will optimize all 3D models in directory "input" to all desired variants (see configuration of variants in previous step), creating a directory "output" with the results. 
   Alternatively, instead of using an input directory, you can also optimize single input files (example: `python3 rpdc.py input/teapot.glb`).  
   ![Illustration of Step 4](/tutorial/quick-intro/images/step4.JPG)
   
 5. That's it! The resulting optimized models should show up in directory "output".  
   ![Illustration of Step 5](/tutorial/quick-intro/images/finished.JPG)
 
 Feel free to use this script as a basis for your own API-based integration, as well as to submit feature requests or pull requests for your changes right here.
 
 
## Advanced Usage
To learn more about the available parameters of the script, use the "help" function:  
`python3 rpdc.py -h` or `python rpdc.py -h` (depending on your Python setup) 

Also, feel free to browse the documented source code, which also helps you to set up your own RapidCompact API integration.

## Translate variants to CLI format
If you want to use your variants.json with the CLI version of RapidCompact, you need to translate it first to the CLI format.
For this you can use the rpdt script in the utils directory of this repository.

### Usage
1. Make sure you have [Python 3](https://www.python.org/) installed.

2. Edit "credentials.json" and enter your [API token](https://app.rapidcompact.com/app/api-tokens).  
  ![Illustration of Step 2](/tutorial/quick-intro/images/step2.JPG)

3. Edit the "variants.json" file to specify the desired resolution and output formats for your models (or keep it as-is for a first test run).  
  ![Illustration of Step 3](/tutorial/quick-intro/images/step3.JPG)
4. Open a command line (for example, using Windows PowerShell) to invoke the `rpdt.py` script.     
   Example:
   `python3 utils/rpdt.py`     
   This will request a translated version of your variants.json configuration and place the CLI configuration of it in the output folder.    
   ![Illustration of Step 4](/tutorial/quick-intro/images/rpdt.png)
5. Open the folders in the output directory to retrieve your cli commands    
   ![Illustration of Step 4](/tutorial/quick-intro/images/rpdtOutput.jpg)