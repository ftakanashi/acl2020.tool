#! /usr/bin/bash

# Adapted from https://github.com/wangqiangneu/dlcl/

set -e

export tools=acl20.tool
export test_tgt_raw=acl20.tool/valid/valid.raw.ja
export reverse=
# task name
export task=zh2ja

# experiment name
export tag=

export data_dir=

# set gpu device
export device=0,1

# save dir
export save_dir=checkpoints/$task/$tag
if [ ! -d $save_dir ]; then
	mkdir -p $save_dir
fi

# current running script
export script=${BASH_SOURCE[0]}


function main {

seed=

### training setting
arch=transformer_wmt_en_de

gpu_num=2
fp16=1
share_embedding=0
dropout=0.2
lr=0.0005
warmup=4000
batch_size=4096
update_freq=64
weight_decay=0.0
saved_checkpoint_num=20
max_epoch=40
max_update=

### decoding setting
whos=(test)
ensemble=5
decoding_batch_size=20
beam=5
length_penalty=1

# copy training script
cp $script $save_dir/train.sh

cmd="python -u train.py data-bin/$data_dir
  --ddp-backend=no_c10d -s zh -t ja
  --arch $arch
  --optimizer adam --clip-norm 0.0
  --lr-scheduler inverse_sqrt --warmup-init-lr 1e-07 --warmup-updates $warmup
  --lr $lr --min-lr 1e-09
  --weight-decay $weight_decay
  --criterion label_smoothed_cross_entropy --label-smoothing 0.1
  --max-tokens $batch_size
  --update-freq $update_freq
  --no-progress-bar
  --log-interval 1000
  --save-dir $save_dir
  --keep-last-epochs $saved_checkpoint_num"

adam_betas="'(0.9, 0.98)'"
cmd=${cmd}" --adam-betas "${adam_betas}
if [ $share_embedding -eq 1 ]; then
cmd=${cmd}" --share-all-embeddings "
fi
if [ -n "$max_epoch" ]; then
cmd=${cmd}" --max-epoch "${max_epoch}
fi
if [ -n "$max_update" ]; then
cmd=${cmd}" --max-update "${max_update}
fi
if [ -n "$fp16" ]; then
cmd=${cmd}" --fp16 "
fi
if [ -n "$dropout" ]; then
cmd=${cmd}" --dropout "${dropout}
fi
if [ -n "$seed" ]; then
cmd=${cmd}" --seed "${seed}
fi

export CUDA_VISIBLE_DEVICES=$device
log=$save_dir/train.log
if [ ! -e $log ]; then
	cmd="nohup "${cmd}" | tee $log &"
	eval $cmd
else
	for i in `seq 1 100`; do
		if [ ! -e $log.$i ]; then
			cmd="nohup "${cmd}" | tee $log.$i &"
			eval $cmd
			break
		fi
	done
fi
# wait for training finished
wait
echo -e " >> finish training \n"

if [ ! -e "$save_dir/$max_epoch.last$ensemble.ensemble.pt" ]; then
	echo -e " >> generate last $ensemble ensemble model for inference \n"
	PYTHONPATH=`pwd` python scripts/average_checkpoints.py --inputs $save_dir --output $save_dir/$max_epoch.last$ensemble.ensemble.pt --num-epoch-checkpoints $ensemble
fi
echo -e

checkpoint=$max_epoch.last$ensemble.ensemble.pt

for ((i=0;i<${#whos[@]};i++));do
{
	# test set
	who=${whos[$i]}
	echo -e " >> translate $who by $checkpoint with batch=$decoding_batch_size beam=$beam alpha=$length_penalty\n"

	# translation log
	output=$save_dir/$who.trans.log

	# use the first gpu to decode
	gpu_id=$(echo $device | cut -d ',' -f 1)
	export CUDA_VISIBLE_DEVICES=$gpu_id

	python -u generate.py \
	data-bin/$data_dir \
	--path $save_dir/$checkpoint \
	--gen-subset $who \
	--batch-size $decoding_batch_size \
	--beam $beam \
	--lenpen $length_penalty \
	--log-format simple \
	-s zh -t ja > $output 2>&1 

	echo -e " >> evaluate bpe bleu $who \n"
	tail -n 1 $output >> $save_dir/train.log
	echo -e

	echo -e " >> save mecab $who \n"
	grep "^H" $output | sed 's/^H-//g' | sort -n | cut -f3 | sed -r 's/(@@ )|(@@ ?$)//g' > $save_dir/$who.tok.hyp
	grep "^T" $output | sed 's/^T-//g' | sort -n | cut -f2 | sed -r 's/(@@ )|(@@ ?$)//g' > $save_dir/$who.tok.ref
	echo -e
	
	if [ $reverse -eq 1 ]; then
		echo -e " >> reverse mecab $who \n"
		mv $save_dir/$who.tok.hyp $save_dir/$who.tok.hyp.r
		python $tools/reverse.py < $save_dir/$who.tok.hyp.r > $save_dir/$who.tok.hyp
		echo -e
	fi
	
	echo -e " >> evaluate mecab bleu $who \n"
	python score.py -r $save_dir/$who.tok.ref -s $save_dir/$who.tok.hyp
	echo -e
	
	echo -e " >> char raw $test_tgt_raw \n"
	python $tools/postedit.py -i ref < $test_tgt_raw > $save_dir/$who.raw.char.ref
	echo -e

	echo -e " >> evaluate char hyp $who \n"
	cat $save_dir/$who.tok.hyp | sed 's/ //g' > $save_dir/$who.hyp
	python $tools/postedit.py -i ref < $save_dir/$who.hyp > $save_dir/$who.char.hyp
	python score.py -r $save_dir/$who.raw.char.ref -s $save_dir/$who.char.hyp
	echo -e

	echo -e " >> evaluate char hyp with postedit $who \n"
	python $tools/postedit.py -i ja < $save_dir/$who.tok.hyp > $save_dir/$who.post.char.hyp
	python score.py -r $save_dir/$who.raw.char.ref -s  $save_dir/$who.post.char.hyp
	echo -e
	
	echo -e " >> evaluate char hyp with postedit & remove period $who \n"
	python $tools/postedit.py --remove-period -i ja < $save_dir/$who.tok.hyp > $save_dir/$who.post_re.char.hyp
	python score.py -r $save_dir/$who.raw.char.ref -s $save_dir/$who.post_re.char.hyp
	echo -e


}
done
}

export -f main
nohup bash -c main >> $save_dir/train.log 2>&1 &
sleep 2 && tail -f  $save_dir/train.log
wait
